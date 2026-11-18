from fastapi.testclient import TestClient

from tesseract.caddy.config import HostSpec, NodeSpec, authelia_handler, build_config
from tests.conftest import FakeCaddy

HOST = {
    "domain": "wiki.example.org",
    "node_id": 1,
    "upstream_host": "10.0.0.5",
    "upstream_port": 8090,
}


def test_handler_shape() -> None:
    h = authelia_handler("https://auth.example.org", ["Remote-User"])
    assert h["upstreams"] == [{"dial": "auth.example.org:443"}]
    assert h["transport"]["tls"] == {}
    assert h["rewrite"] == {"method": "GET", "uri": "/api/authz/forward-auth"}
    routes = h["handle_response"][0]["routes"]
    # Header wird erst gelöscht (gegen Fälschung), dann aus Authelias Antwort gesetzt
    assert routes[1]["handle"][0]["request"] == {"delete": ["Remote-User"]}
    assert routes[2]["handle"][0]["request"]["set"]["Remote-User"] == [
        "{http.reverse_proxy.header.Remote-User}"
    ]
    plain = authelia_handler("http://authelia:9091", [])
    assert plain["upstreams"] == [{"dial": "authelia:9091"}] and "transport" not in plain


def test_order_and_missing_url() -> None:
    host = HostSpec(1, "a.example.org", "http", "10.0.0.1", 80, waf_mode="block", authelia=True)
    cfg = build_config(
        NodeSpec(admin_listen="x", hosts=[host], authelia_url="http://authelia:9091")
    )
    routes = cfg["apps"]["http"]["servers"]["https"]["routes"][0]["handle"][0]["routes"]
    assert [r["handle"][0]["handler"] for r in routes] == ["waf", "reverse_proxy", "reverse_proxy"]
    assert routes[1]["handle"][0]["rewrite"]["uri"] == "/api/authz/forward-auth"

    # Ohne Authelia-Adresse: lieber gesperrt als offen
    cfg = build_config(NodeSpec(admin_listen="x", hosts=[host]))
    routes = cfg["apps"]["http"]["servers"]["https"]["routes"][0]["handle"][0]["routes"]
    assert routes[1]["handle"][0]["status_code"] == 503


def test_api(auth_client: TestClient, caddy: FakeCaddy) -> None:
    r = auth_client.post("/api/hosts", json={**HOST, "authelia": True})
    assert r.status_code == 409  # erst Adresse eintragen

    for bad in ("authelia", "ftp://x", "https://auth.example.org/pfad"):
        r = auth_client.put("/api/settings/general", json={"authelia_url": bad})
        assert r.status_code == 422, bad
    r = auth_client.put(
        "/api/settings/general",
        json={"authelia_url": "https://auth.example.org/", "authelia_headers": ["Remote-User"]},
    )
    assert r.json()["authelia_url"] == "https://auth.example.org"

    host = auth_client.post("/api/hosts", json={**HOST, "authelia": True}).json()["host"]
    assert host["authelia"] is True
    routes = caddy.last["apps"]["http"]["servers"]["https"]["routes"]
    route = next(r for r in routes if r["match"][0]["host"] == ["wiki.example.org"])
    assert "/api/authz/forward-auth" in str(route)

    # Adresse entfernen, solange Hosts sie nutzen → abgelehnt
    r = auth_client.put("/api/settings/general", json={"authelia_url": ""})
    assert r.status_code == 409
    auth_client.put(f"/api/hosts/{host['id']}", json={**HOST, "authelia": False})
    assert auth_client.put("/api/settings/general", json={"authelia_url": ""}).status_code == 200


def test_test_endpoint_without_url(auth_client: TestClient) -> None:
    assert auth_client.post("/api/settings/authelia/test").json()["ok"] is False
