from fastapi.testclient import TestClient

from tesseract.caddy.config import FINGERPRINT, AreaSpec, HostSpec, NodeSpec, build_config
from tests.conftest import FakeCaddy

HOST = {
    "domain": "app.example.org",
    "node_id": 1,
    "upstream_host": "10.0.0.5",
    "upstream_port": 8080,
    "waf_mode": "block",
}


def _routes(cfg: dict, domain: str) -> list[dict]:
    routes = cfg["apps"]["http"]["servers"]["https"]["routes"]
    return next(r for r in routes if r["match"][0]["host"] == [domain])["handle"][0]["routes"]


def _handlers(routes: list[dict]) -> list[str]:
    return [h["handler"] for r in routes for h in r["handle"]]


def test_area_overrides() -> None:
    host = HostSpec(
        1,
        "app.example.org",
        "http",
        "10.0.0.5",
        8080,
        waf_mode="block",
        areas=(
            AreaSpec(paths=("/api",), waf_mode="off"),
            AreaSpec(paths=("/admin",), access="mtls", allowed=(("ab" * 32, "PEM"),)),
            AreaSpec(paths=("/intern",), ip_mode="allow", ip_ranges=("10.99.0.0/16",)),
        ),
    )
    cfg = build_config(NodeSpec(admin_listen="x", hosts=[host], client_ca_der_b64="AA=="))
    routes = _routes(cfg, "app.example.org")
    api, admin, intern, *default = routes
    assert api["match"] == [{"path": ["/api", "/api/*"]}]
    assert "waf" not in _handlers(api["handle"][0]["routes"])
    admin_gate = admin["handle"][0]["routes"][0]
    assert admin_gate["match"][0]["not"][0]["vars"][FINGERPRINT] == ["ab" * 32]
    assert _handlers(intern["handle"][0]["routes"])[0] == "static_response"
    assert "waf" in _handlers(default)

    # Bereich mit Zertifikat → TLS-Richtlinie fragt nach Zertifikaten, ohne Handshake-Abbruch
    policy = cfg["apps"]["http"]["servers"]["https"]["tls_connection_policies"][0]
    assert policy["client_authentication"]["mode"] == "verify_if_given"


def test_strict_host_with_public_area_is_not_strict() -> None:
    host = HostSpec(
        1,
        "a.example.org",
        "http",
        "10.0.0.1",
        80,
        access="mtls",
        areas=(AreaSpec(paths=("/.well-known",), access="public"),),
    )
    assert host.strict is False


def test_api_roundtrip_and_versions(auth_client: TestClient, caddy: FakeCaddy) -> None:
    assert (
        auth_client.post("/api/ca/setup", json={"passphrase": "root-passphrase-123"}).status_code
        == 200
    )
    ben = auth_client.post("/api/persons", json={"name": "Ben"}).json()
    auth_client.post(f"/api/persons/{ben['id']}/devices", json={"name": "Laptop"})

    areas = [
        {"name": "API", "paths": ["api"], "waf_mode": "off"},
        {"name": "Admin", "paths": ["/admin"], "access": "mtls", "grant_person_ids": [ben["id"]]},
    ]
    r = auth_client.post("/api/hosts", json={**HOST, "areas": areas})
    assert r.status_code == 201, r.text
    host = r.json()["host"]
    assert [a["name"] for a in host["areas"]] == ["API", "Admin"]
    assert host["areas"][0]["paths"] == ["/api"]

    routes = _routes(caddy.last, "app.example.org")
    fps = routes[1]["handle"][0]["routes"][0]["match"][0]["not"][0]["vars"][FINGERPRINT]
    assert len(fps) == 1 and fps[0] != "-"

    # Bereich entfernen → neue Version mit Änderung „areas“
    r = auth_client.put(f"/api/hosts/{host['id']}", json={**HOST, "areas": areas[:1]})
    v = auth_client.get(f"/api/hosts/{host['id']}/versions").json()[0]
    assert [c["field"] for c in v["changes"]] == ["areas"]
    assert v["changes"][0]["before"][1]["grants"] == ["Ben"]

    restored = auth_client.post(f"/api/hosts/{host['id']}/versions/1/restore").json()["host"]
    assert len(restored["areas"]) == 2 and restored["areas"][1]["grant_person_ids"] == [ben["id"]]


def test_area_validation(auth_client: TestClient) -> None:
    bad = [
        [{"paths": []}],
        [{"paths": ["/a b"]}],
        [{"paths": ["/x"], "ip_mode": "allow"}],
        [{"paths": ["/x"], "grant_group_ids": [999]}],
    ]
    for areas in bad:
        r = auth_client.post("/api/hosts", json={**HOST, "areas": areas})
        assert r.status_code == 422, areas
