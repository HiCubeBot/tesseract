"""DNS-Einträge für Hosts automatisch bei Cloudflare – gegen eine nachgebaute API."""

import json
import uuid

import httpx
from fastapi.testclient import TestClient

from tesseract import dnsrecords as dr

TOKEN = "cf-token-123"


class FakeCloudflare:
    def __init__(self) -> None:
        self.zones = {"beispiel.de": "zone-1"}
        self.records: dict[str, dict] = {}
        self.calls: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        path = request.url.path.removeprefix("/client/v4")
        self.calls.append(f"{request.method} {path}")

        def ok(result):
            return httpx.Response(200, json={"success": True, "errors": [], "result": result})

        if path == "/zones":
            name = request.url.params["name"]
            return ok([{"id": self.zones[name], "name": name}] if name in self.zones else [])
        if path.endswith("/dns_records") and request.method == "GET":
            name = request.url.params["name"]
            return ok([r for r in self.records.values() if r["name"] == name])
        if path.endswith("/dns_records") and request.method == "POST":
            body = json.loads(request.content)
            rid = uuid.uuid4().hex
            self.records[rid] = {"id": rid, **body}
            return ok(self.records[rid])
        rid = path.rsplit("/", 1)[-1]
        if rid not in self.records:
            return httpx.Response(
                404, json={"success": False, "errors": [{"code": 81044, "message": "not found"}]}
            )
        if request.method == "PATCH":
            self.records[rid].update(json.loads(request.content))
            return ok(self.records[rid])
        if request.method == "DELETE":
            del self.records[rid]
            return ok({"id": rid})
        return httpx.Response(400)

    def by_name(self, name):
        return sorted(
            (r["type"], r["content"], r["proxied"])
            for r in self.records.values()
            if r["name"] == name
        )


def _setup(c: TestClient, **zone) -> FakeCloudflare:
    cf = FakeCloudflare()
    c.app.state.dns_transport = httpx.MockTransport(cf.handler)
    assert c.put("/api/settings/general", json={"cloudflare_token": TOKEN}).status_code == 200
    z = {"zone": "beispiel.de", "type": "cname", "cname_target": "home.beispiel.de", **zone}
    r = c.put("/api/settings/dns-zones", json={"zones": [z]})
    assert r.status_code == 200, r.text
    return cf


def _host(c: TestClient, domain="musik.beispiel.de", **kw):
    node = c.get("/api/nodes").json()[0]["id"]
    body = {
        "domain": domain,
        "node_id": node,
        "upstream_host": "10.0.0.5",
        "upstream_port": 80,
        **kw,
    }
    return c.post("/api/hosts", json=body)


def _put(c: TestClient, h: dict, **over):
    skip = {
        "id",
        "node",
        "grants",
        "granted_persons",
        "allowed_devices",
        "wildcard_cert",
        "version",
        "created_at",
        "updated_at",
        "source",
        "source_ref",
        "source_disabled",
        "dns_records",
        "dns_error",
    }
    b = {k: v for k, v in h.items() if k not in skip}
    b.update(node_id=h["node"]["id"], grant_group_ids=[], grant_person_ids=[], areas=[], **over)
    return c.put(f"/api/hosts/{h['id']}", json=b)


def test_zone_settings(auth_client: TestClient) -> None:
    put = auth_client.put
    assert (
        put("/api/settings/dns-zones", json={"zones": [{"zone": "x", "type": "cname"}]}).status_code
        == 422
    )
    r = put("/api/settings/dns-zones", json={"zones": [{"zone": "beispiel.de", "type": "cname"}]})
    assert r.status_code == 422 and "Ziel" in r.json()["detail"]
    r = put(
        "/api/settings/dns-zones",
        json={
            "zones": [
                {
                    "zone": "Beispiel.de.",
                    "type": "address",
                    "ip_source": "custom",
                    "ips": ["203.0.113.7", "2001:db8::7"],
                }
            ]
        },
    )
    assert r.json()["zones"][0]["zone"] == "beispiel.de"
    assert dr.zone_for("a.home.beispiel.de", r.json()["zones"])["zone"] == "beispiel.de"
    assert dr.zone_for("andere.de", r.json()["zones"]) is None


def test_cname_lifecycle(auth_client: TestClient) -> None:
    c = auth_client
    cf = _setup(c)
    r = _host(c, dns_type="cname")
    assert r.status_code == 201, r.text
    assert r.json()["dns"]["ok"] is True
    assert cf.by_name("musik.beispiel.de") == [("CNAME", "home.beispiel.de", False)]
    h = r.json()["host"]
    assert h["dns_records"][0]["type"] == "CNAME"
    rec = next(iter(cf.records.values()))
    assert rec["comment"] == "Tesseract: musik.beispiel.de" and rec["ttl"] == 1

    # eigenes Ziel für diesen Host → Eintrag wird angepasst (gleiche ID)
    rid = rec["id"]
    r = _put(c, h, dns_target="nas.beispiel.de")
    assert r.json()["dns"]["ok"] and cf.by_name("musik.beispiel.de") == [
        ("CNAME", "nas.beispiel.de", False)
    ]
    assert rid in cf.records

    # auf A/AAAA mit den IPs des Nodes umstellen
    node = c.get("/api/nodes").json()[0]
    c.put(
        f"/api/nodes/{node['id']}",
        json={"name": node["name"], "location": "", "public_ips": ["203.0.113.7", "2001:db8::7"]},
    )
    r = _put(c, r.json()["host"], dns_type="address", dns_target="")
    assert r.json()["dns"]["ok"], r.json()
    assert cf.by_name("musik.beispiel.de") == [
        ("A", "203.0.113.7", False),
        ("AAAA", "2001:db8::7", False),
    ]

    # Domain ändern → alte Einträge weg, neue angelegt
    r = _put(c, r.json()["host"], domain="lieder.beispiel.de")
    assert cf.by_name("musik.beispiel.de") == []
    assert len(cf.by_name("lieder.beispiel.de")) == 2

    # Löschen → Einträge weg
    assert c.delete(f"/api/hosts/{r.json()['host']['id']}").status_code == 200
    assert cf.records == {}


def test_draft_conflict_and_adopt(auth_client: TestClient) -> None:
    c = auth_client
    cf = _setup(c)
    # Entwurf → noch kein Eintrag; Anlegen & übertragen → Eintrag
    r = _host(c, dns_type="cname", draft=True)
    assert cf.records == {}
    r = _put(c, r.json()["host"], draft=False)
    assert cf.by_name("musik.beispiel.de") == [("CNAME", "home.beispiel.de", False)]

    # fremder A-Eintrag → Konflikt, Host trotzdem gespeichert, Fehler am Host
    cf.records["fremd"] = {
        "id": "fremd",
        "type": "A",
        "name": "wiki.beispiel.de",
        "content": "198.51.100.1",
        "proxied": False,
    }
    r = _host(c, domain="wiki.beispiel.de", dns_type="cname")
    assert r.status_code == 201
    assert r.json()["dns"]["ok"] is False and "nicht von Tesseract" in r.json()["dns"]["error"]
    h = r.json()["host"]
    assert h["dns_error"] and cf.records["fremd"]["content"] == "198.51.100.1"
    # bei Cloudflare gelöscht → erneut speichern legt an
    del cf.records["fremd"]
    r = _put(c, h)
    assert r.json()["dns"]["ok"] and r.json()["host"]["dns_error"] is None

    # fremder Eintrag mit genau dem gewünschten Wert → wird übernommen, nicht doppelt angelegt
    cf.records["gleich"] = {
        "id": "gleich",
        "type": "CNAME",
        "name": "git.beispiel.de",
        "content": "home.beispiel.de",
        "proxied": False,
    }
    r = _host(c, domain="git.beispiel.de", dns_type="cname")
    assert r.json()["dns"]["ok"] and len(cf.by_name("git.beispiel.de")) == 1
    assert r.json()["host"]["dns_records"][0]["id"] == "gleich"


def test_rules(auth_client: TestClient) -> None:
    c = auth_client
    _setup(c)
    # Proxy + mTLS geht nicht
    r = _host(c, dns_type="cname", dns_proxied=True, access="mtls")
    assert r.status_code == 422 and "Cloudflare-Proxy" in r.text
    # Domain ohne Zone → Fehler am Host
    r = _host(c, domain="musik.andere.de", dns_type="cname")
    assert r.status_code == 201 and "keine Domain" in r.json()["dns"]["error"]
    # address ohne IPs am Node
    r = _host(c, domain="foto.beispiel.de", dns_type="address")
    assert "keine IP" in r.json()["dns"]["error"]
    # Zone prüfen
    assert (
        c.post("/api/settings/dns-zones/check", json={"zone": "beispiel.de"}).json()["ok"] is True
    )
    bad = c.post("/api/settings/dns-zones/check", json={"zone": "fremd.de"}).json()
    assert bad["ok"] is False and "nicht gefunden" in bad["error"]


def test_check_shows_planned_record(auth_client: TestClient) -> None:
    _setup(auth_client)
    node = auth_client.get("/api/nodes").json()[0]["id"]
    body = {"domain": "musik.beispiel.de", "node_id": node, "dns_type": "cname"}
    checks = auth_client.post("/api/hosts/check", json=body).json()
    dns = next(c for c in checks if c["key"] == "dns")
    assert dns["status"] == "ok" and "CNAME → home.beispiel.de" in dns["detail"]
    body["dns_type"] = "address"
    dns = next(
        c for c in auth_client.post("/api/hosts/check", json=body).json() if c["key"] == "dns"
    )
    assert dns["status"] == "warn" and "keine IP" in dns["detail"]
