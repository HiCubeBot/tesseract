from fastapi.testclient import TestClient

from tests.conftest import FakeCaddy

HOST = {
    "domain": "Musik.Example.org",
    "node_id": 1,
    "upstream_scheme": "http",
    "upstream_host": "10.0.1.20",
    "upstream_port": 4533,
}


def _create(client: TestClient, **kw) -> dict:
    r = client.post("/api/hosts", json={**HOST, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def _domains(config: dict) -> list[str]:
    routes = config["apps"]["http"]["servers"]["https"]["routes"]
    return [r["match"][0]["host"][0] for r in routes]


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/hosts").status_code == 401


def test_create_applies_config(auth_client: TestClient, caddy: FakeCaddy) -> None:
    saved = _create(auth_client)
    assert saved["host"]["domain"] == "musik.example.org"
    assert saved["host"]["node"]["name"] == "local"
    assert saved["apply"] == {"ok": True, "error": None, "skipped": False}
    assert _domains(caddy.last) == ["tesseract.example.org", "musik.example.org"]

    nodes = auth_client.get("/api/nodes").json()
    assert nodes[0]["hosts"] == 1 and nodes[0]["in_sync"] is True


def test_draft_is_not_applied(auth_client: TestClient, caddy: FakeCaddy) -> None:
    saved = _create(auth_client, draft=True)
    assert saved["apply"]["skipped"] is True
    assert caddy.loaded == []


def test_validation(auth_client: TestClient) -> None:
    bad = [
        {"domain": "nicht gültig"},
        {"upstream_host": "http://10.0.0.1"},
        {"upstream_port": 0},
        {"node_id": 99},
        {"domain": "tesseract.example.org"},
    ]
    for patch in bad:
        r = auth_client.post("/api/hosts", json={**HOST, **patch})
        assert r.status_code in (409, 422), (patch, r.status_code)


def test_duplicate_domain(auth_client: TestClient) -> None:
    _create(auth_client)
    assert auth_client.post("/api/hosts", json=HOST).status_code == 409


def test_update_versions_and_restore(auth_client: TestClient, caddy: FakeCaddy) -> None:
    host_id = _create(auth_client)["host"]["id"]

    r = auth_client.put(f"/api/hosts/{host_id}", json={**HOST, "upstream_port": 4534})
    assert r.json()["host"]["version"] == 2

    # Unveränderte Daten erzeugen keine neue Version
    r = auth_client.put(f"/api/hosts/{host_id}", json={**HOST, "upstream_port": 4534})
    assert r.json()["host"]["version"] == 2 and r.json()["apply"]["skipped"]

    versions = auth_client.get(f"/api/hosts/{host_id}/versions").json()
    assert [v["version"] for v in versions] == [2, 1]
    assert versions[0]["changes"] == [{"field": "upstream_port", "before": 4533, "after": 4534}]
    assert versions[0]["current"] is True

    detail = auth_client.get(f"/api/hosts/{host_id}/versions/2").json()
    assert "4534" in str(detail["route"]) and "4533" in str(detail["previous_route"])

    r = auth_client.post(f"/api/hosts/{host_id}/versions/1/restore")
    assert r.status_code == 200
    assert r.json()["host"]["version"] == 3
    assert r.json()["host"]["upstream_port"] == 4533
    assert "10.0.1.20:4533" in str(caddy.last)

    audit = [e["action"] for e in auth_client.get("/api/audit").json()]
    assert audit[:3] == ["host_restored", "host_updated", "host_created"]


def test_delete(auth_client: TestClient, caddy: FakeCaddy) -> None:
    host_id = _create(auth_client)["host"]["id"]
    assert auth_client.delete(f"/api/hosts/{host_id}").json()["ok"] is True
    assert _domains(caddy.last) == ["tesseract.example.org"]
    assert auth_client.get(f"/api/hosts/{host_id}").status_code == 404


def test_apply_error_is_reported(auth_client: TestClient, caddy: FakeCaddy) -> None:
    caddy.fail_with = "loading config: kaputt"
    saved = _create(auth_client)
    assert saved["apply"]["ok"] is False
    assert "kaputt" in saved["apply"]["error"]
    node = auth_client.get("/api/nodes").json()[0]
    assert node["in_sync"] is False and "kaputt" in node["last_apply_error"]

    caddy.fail_with = None
    assert auth_client.post("/api/nodes/1/apply").json() == {"ok": True, "error": None}


def test_checks(auth_client: TestClient) -> None:
    _create(auth_client)
    r = auth_client.post(
        "/api/hosts/check",
        json={"domain": "musik.example.org", "upstream_host": "127.0.0.1", "upstream_port": 1},
    )
    by_key = {c["key"]: c for c in r.json()}
    assert by_key["domain_free"]["status"] == "bad"
    assert by_key["upstream"]["status"] == "warn"
    assert "dns" in by_key


def test_settings(auth_client: TestClient, caddy: FakeCaddy) -> None:
    _create(auth_client)
    r = auth_client.put(
        "/api/settings/general",
        json={"acme_email": "admin@example.org", "public_ips": ["203.0.113.7"]},
    )
    assert r.status_code == 200
    assert r.json()["controller_domain"] == "tesseract.example.org"
    issuer = caddy.last["apps"]["tls"]["automation"]["policies"][0]["issuers"][0]
    assert issuer["email"] == "admin@example.org"
    r = auth_client.put("/api/settings/general", json={"public_ips": ["keine-ip"]})
    assert r.status_code == 422


def test_settings_partial_update(auth_client: TestClient) -> None:
    auth_client.put(
        "/api/settings/general",
        json={"waf_default_mode": "block", "authelia_url": "http://authelia:9091"},
    )
    # Seite „Allgemein“ schickt nur ihre Felder – der Rest bleibt erhalten
    r = auth_client.put("/api/settings/general", json={"acme_email": "x@example.org"})
    g = r.json()
    assert g["acme_email"] == "x@example.org"
    assert g["waf_default_mode"] == "block"
    assert g["authelia_url"] == "http://authelia:9091"
