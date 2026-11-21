"""Hosts mit mTLS: Freigaben, Pfade, Geräte-Listen in der Caddy-Config."""

from fastapi.testclient import TestClient

from tesseract.caddy.config import FINGERPRINT, HostSpec, NodeSpec, build_config, path_patterns
from tests.conftest import FakeCaddy

HOST = {
    "domain": "fotos.example.org",
    "node_id": 1,
    "upstream_host": "10.0.1.20",
    "upstream_port": 2342,
}


def _setup(c: TestClient) -> dict:
    assert c.post("/api/ca/setup", json={"passphrase": "root-passphrase-123"}).status_code == 200
    fam = c.post("/api/groups", json={"name": "Familie"}).json()
    anna = c.post("/api/persons", json={"name": "Anna", "group_ids": [fam["id"]]}).json()
    ben = c.post("/api/persons", json={"name": "Ben"}).json()
    return {"fam": fam, "anna": anna, "ben": ben}


def _issue(c: TestClient, person_id: int, name: str) -> dict:
    r = c.post(f"/api/persons/{person_id}/devices", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["device"]


def _fp(device: dict) -> str:
    return device["fingerprint"].replace(":", "").lower()


def _https(caddy: FakeCaddy) -> dict:
    return caddy.last["apps"]["http"]["servers"]["https"]


def _policy(caddy: FakeCaddy, domain: str) -> dict:
    for p in _https(caddy).get("tls_connection_policies", []):
        if p.get("match", {}).get("sni") == [domain]:
            return p["client_authentication"]
    raise AssertionError(f"keine TLS-Richtlinie für {domain}")


def _gate(caddy: FakeCaddy, domain: str) -> dict:
    for r in _https(caddy)["routes"]:
        if r["match"][0]["host"] == [domain]:
            return r["handle"][0]["routes"][0]
    raise AssertionError(domain)


def test_mtls_host_lists_granted_devices(auth_client: TestClient, caddy: FakeCaddy) -> None:
    ids = _setup(auth_client)
    anna_phone = _issue(auth_client, ids["anna"]["id"], "iPhone")
    _issue(auth_client, ids["ben"]["id"], "Laptop")

    r = auth_client.post(
        "/api/hosts", json={**HOST, "access": "mtls", "grant_group_ids": [ids["fam"]["id"]]}
    )
    assert r.status_code == 201, r.text
    host = r.json()["host"]
    assert host["granted_persons"] == 1 and host["allowed_devices"] == 1
    assert host["grants"] == [{"kind": "group", "id": ids["fam"]["id"], "name": "Familie"}]

    policy = _policy(caddy, "fotos.example.org")
    assert policy["mode"] == "require_and_verify"
    certs = policy["verifiers"][0]["leaf_certs_loaders"][0]["certificates"]
    assert len(certs) == 1 and "BEGIN CERTIFICATE" in certs[0]
    assert _gate(caddy, "fotos.example.org")["match"][0]["not"][0]["vars"][FINGERPRINT] == [
        _fp(anna_phone)
    ]
    # Catch-all-Richtlinie für alle anderen Hosts
    assert _https(caddy)["tls_connection_policies"][-1] == {}

    # Neues Gerät von Anna → automatisch in der Liste
    tablet = _issue(auth_client, ids["anna"]["id"], "Tablet")
    fps = _gate(caddy, "fotos.example.org")["match"][0]["not"][0]["vars"][FINGERPRINT]
    assert set(fps) == {_fp(anna_phone), _fp(tablet)}

    # Sperren → sofort raus
    auth_client.post(f"/api/devices/{anna_phone['id']}/revoke", json={})
    fps = _gate(caddy, "fotos.example.org")["match"][0]["not"][0]["vars"][FINGERPRINT]
    assert fps == [_fp(tablet)]

    # Person sperren → keine Geräte mehr
    auth_client.put(
        f"/api/persons/{ids['anna']['id']}",
        json={"name": "Anna", "group_ids": [ids["fam"]["id"]], "disabled": True},
    )
    fps = _gate(caddy, "fotos.example.org")["match"][0]["not"][0]["vars"][FINGERPRINT]
    assert fps == ["-"]
    assert "verifiers" not in _policy(caddy, "fotos.example.org")


def test_hint_page_uses_verify_if_given(auth_client: TestClient, caddy: FakeCaddy) -> None:
    ids = _setup(auth_client)
    auth_client.post(
        "/api/hosts",
        json={
            **HOST,
            "access": "mtls",
            "no_cert_action": "hint",
            "grant_person_ids": [ids["ben"]["id"]],
        },
    )
    assert _policy(caddy, "fotos.example.org")["mode"] == "verify_if_given"
    deny = _gate(caddy, "fotos.example.org")["handle"][0]
    assert deny["status_code"] == 403 and "Kein Zugang" in deny["body"]


def test_public_host_with_protected_path(auth_client: TestClient, caddy: FakeCaddy) -> None:
    ids = _setup(auth_client)
    r = auth_client.post(
        "/api/hosts",
        json={
            **HOST,
            "access": "public",
            "paths": ["/admin", "api/intern/*"],
            "grant_person_ids": [ids["ben"]["id"]],
            "force_https": False,
        },
    )
    assert r.json()["host"]["paths"] == ["/admin", "/api/intern/*"]
    gate = _gate(caddy, "fotos.example.org")
    assert gate["match"][0]["path"] == ["/admin", "/admin/*", "/api/intern/*"]
    assert _policy(caddy, "fotos.example.org")["mode"] == "verify_if_given"
    # Trotz force_https=False: geschützter Host wird auf :80 umgeleitet
    http_route = caddy.last["apps"]["http"]["servers"]["http"]["routes"][-1]
    assert http_route["handle"][0]["status_code"] == 308


def test_mtls_host_with_public_path(auth_client: TestClient, caddy: FakeCaddy) -> None:
    _setup(auth_client)
    auth_client.post("/api/hosts", json={**HOST, "access": "mtls", "paths": ["/api"]})
    negations = _gate(caddy, "fotos.example.org")["match"][0]["not"]
    assert negations[1] == {"path": ["/api", "/api/*"]}
    # Mit öffentlichen Pfaden kann der Handshake nicht scheitern
    assert _policy(caddy, "fotos.example.org")["mode"] == "verify_if_given"


def test_invalid_paths(auth_client: TestClient) -> None:
    for bad in (["/a b"], ["/<script>"], ["/" + "x" * 300]):
        r = auth_client.post("/api/hosts", json={**HOST, "access": "mtls", "paths": bad})
        assert r.status_code == 422, bad


def test_unknown_grant(auth_client: TestClient) -> None:
    r = auth_client.post("/api/hosts", json={**HOST, "access": "mtls", "grant_group_ids": [99]})
    assert r.status_code == 422


def test_grants_in_versions_and_restore(auth_client: TestClient, caddy: FakeCaddy) -> None:
    ids = _setup(auth_client)
    host = auth_client.post(
        "/api/hosts", json={**HOST, "access": "mtls", "grant_group_ids": [ids["fam"]["id"]]}
    ).json()["host"]
    auth_client.put(
        f"/api/hosts/{host['id']}",
        json={**HOST, "access": "mtls", "grant_person_ids": [ids["ben"]["id"]]},
    )
    v = auth_client.get(f"/api/hosts/{host['id']}/versions").json()[0]
    assert v["changes"] == [{"field": "grants", "before": ["Gruppe Familie"], "after": ["Ben"]}]
    restored = auth_client.post(f"/api/hosts/{host['id']}/versions/1/restore").json()["host"]
    assert restored["grants"][0]["name"] == "Familie"


def test_access_matrix(auth_client: TestClient, caddy: FakeCaddy) -> None:
    ids = _setup(auth_client)
    _issue(auth_client, ids["ben"]["id"], "Laptop")
    pub = auth_client.post("/api/hosts", json={**HOST, "domain": "blog.example.org"}).json()
    sec = auth_client.post("/api/hosts", json={**HOST, "access": "mtls"}).json()["host"]

    m = auth_client.get("/api/access").json()
    assert [h["domain"] for h in m["hosts"]] == ["fotos.example.org"]
    assert {g["name"] for g in m["groups"]} == {"Admin", "Familie"}
    assert m["grants"] == []

    r = auth_client.put(
        "/api/access",
        json={"grants": [{"host_id": sec["id"], "kind": "person", "id": ids["ben"]["id"]}]},
    )
    assert r.json()["changed"] == ["fotos.example.org"]
    assert auth_client.get(f"/api/hosts/{sec['id']}").json()["allowed_devices"] == 1
    assert auth_client.get("/api/access").json()["grants"] == [
        {"host_id": sec["id"], "kind": "person", "id": ids["ben"]["id"]}
    ]
    # Öffentliche Hosts sind nicht Teil der Matrix
    r = auth_client.put(
        "/api/access",
        json={"grants": [{"host_id": pub["host"]["id"], "kind": "person", "id": ids["ben"]["id"]}]},
    )
    assert r.status_code == 422


def test_without_ca_mtls_host_is_closed() -> None:
    cfg = build_config(
        NodeSpec(
            admin_listen="x",
            hosts=[HostSpec(1, "a.example.org", "http", "10.0.0.1", 80, access="mtls")],
        )
    )
    server = cfg["apps"]["http"]["servers"]["https"]
    assert "tls_connection_policies" not in server
    gate = server["routes"][0]["handle"][0]["routes"][0]
    assert gate["match"][0]["not"][0]["vars"][FINGERPRINT] == ["-"]


def test_path_patterns() -> None:
    assert path_patterns(["/admin", "/admin/", "/x/*", "/"]) == [
        "/admin",
        "/admin/*",
        "/x/*",
        "/",
        "/*",
    ]


def test_internal_networks_without_certificate(auth_client: TestClient, caddy: FakeCaddy) -> None:
    ids = _setup(auth_client)
    body = {
        **HOST,
        "access": "mtls",
        "grant_person_ids": [ids["ben"]["id"]],
        "internal_no_cert": True,
    }
    # ohne interne Netze nicht möglich
    r = auth_client.post("/api/hosts", json=body)
    assert r.status_code == 409 and "internen Netze" in r.json()["detail"]
    auth_client.put("/api/settings/general", json={"internal_networks": ["192.168.178.0/24"]})
    r = auth_client.post("/api/hosts", json=body)
    assert r.status_code == 201, r.text
    assert r.json()["host"]["internal_no_cert"] is True

    # Handshake ohne Zertifikat muss gehen, die Sperre lässt das interne Netz durch
    assert _policy(caddy, "fotos.example.org")["mode"] == "verify_if_given"
    nots = _gate(caddy, "fotos.example.org")["match"][0]["not"]
    assert {"remote_ip": {"ranges": ["192.168.178.0/24"]}} in nots

    # ausschalten → wieder streng
    h = r.json()["host"]
    put = {
        **body,
        "internal_no_cert": False,
        "grant_group_ids": [],
    }
    assert auth_client.put(f"/api/hosts/{h['id']}", json=put).status_code == 200
    assert _policy(caddy, "fotos.example.org")["mode"] == "require_and_verify"
    nots = _gate(caddy, "fotos.example.org")["match"][0]["not"]
    assert not any("remote_ip" in n for n in nots)
    versions = auth_client.get(f"/api/hosts/{h['id']}/versions").json()
    assert versions[0]["changes"][0]["field"] == "internal_no_cert"
