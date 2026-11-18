from fastapi.testclient import TestClient

from tesseract.caddy.config import HostSpec, NodeSpec, build_config
from tests.conftest import FakeCaddy

HOST = {
    "domain": "status.example.org",
    "node_id": 1,
    "upstream_host": "10.0.0.5",
    "upstream_port": 3001,
}


def _first_route(caddy: FakeCaddy, domain: str) -> dict:
    routes = caddy.last["apps"]["http"]["servers"]["https"]["routes"]
    route = next(r for r in routes if r["match"][0]["host"] == [domain])
    return route["handle"][0]["routes"][0]


def test_block_and_allow_matchers() -> None:
    def first(**kw):
        host = HostSpec(1, "a.example.org", "http", "10.0.0.1", 80, **kw)
        cfg = build_config(NodeSpec(admin_listen="x", hosts=[host]))
        return cfg["apps"]["http"]["servers"]["https"]["routes"][0]["handle"][0]["routes"][0]

    block = first(ip_mode="block", ip_ranges=("198.51.100.0/24",))
    assert block["match"] == [{"client_ip": {"ranges": ["198.51.100.0/24"]}}]
    allow = first(ip_mode="allow", ip_ranges=("192.168.178.0/24",))
    assert allow["match"] == [{"not": [{"client_ip": {"ranges": ["192.168.178.0/24"]}}]}]
    assert allow["handle"][0]["status_code"] == 403
    # Leere Sperrliste → kein Filter
    assert "client_ip" not in str(first(ip_mode="block", ip_ranges=()))


def test_trusted_proxies() -> None:
    cfg = build_config(NodeSpec(admin_listen="x", trusted_proxies=("173.245.48.0/20",)))
    for name in ("https", "http"):
        server = cfg["apps"]["http"]["servers"][name]
        assert server["trusted_proxies"] == {"source": "static", "ranges": ["173.245.48.0/20"]}


def test_lists_and_hosts(auth_client: TestClient, caddy: FakeCaddy) -> None:
    r = auth_client.post(
        "/api/ip-lists", json={"name": "Scanner", "entries": ["198.51.100.7", "203.0.113.5/24"]}
    )
    assert r.status_code == 201, r.text
    scanner = r.json()
    assert scanner["entries"] == ["198.51.100.7/32", "203.0.113.0/24"]
    assert auth_client.post("/api/ip-lists", json={"name": "Scanner"}).status_code == 409
    assert (
        auth_client.post("/api/ip-lists", json={"name": "X", "entries": ["keine"]}).status_code
        == 422
    )

    host = auth_client.post(
        "/api/hosts",
        json={
            **HOST,
            "ip_mode": "block",
            "ip_entries": ["192.0.2.1"],
            "ip_list_ids": [scanner["id"]],
        },
    ).json()["host"]
    assert host["ip_entries"] == ["192.0.2.1/32"]
    first = _first_route(caddy, "status.example.org")
    assert first["match"][0]["client_ip"]["ranges"] == [
        "192.0.2.1/32",
        "198.51.100.7/32",
        "203.0.113.0/24",
    ]

    # Liste ändern → alle Hosts mit dieser Liste werden neu übertragen
    auth_client.put(
        f"/api/ip-lists/{scanner['id']}", json={"name": "Scanner", "entries": ["198.51.100.8"]}
    )
    first = _first_route(caddy, "status.example.org")
    assert first["match"][0]["client_ip"]["ranges"] == ["192.0.2.1/32", "198.51.100.8/32"]

    # Benutzte Liste lässt sich nicht löschen
    r = auth_client.delete(f"/api/ip-lists/{scanner['id']}")
    assert r.status_code == 409 and "status.example.org" in r.json()["detail"]

    # Verlauf zeigt Listen mit Namen
    auth_client.put(f"/api/hosts/{host['id']}", json={**HOST, "ip_mode": "off"})
    v = auth_client.get(f"/api/hosts/{host['id']}/versions").json()[0]
    changes = {c["field"]: c for c in v["changes"]}
    assert changes["ip_lists"]["before"] == ["Scanner"]
    assert auth_client.delete(f"/api/ip-lists/{scanner['id']}").status_code == 204


def test_allow_needs_entries(auth_client: TestClient) -> None:
    r = auth_client.post("/api/hosts", json={**HOST, "ip_mode": "allow"})
    assert r.status_code == 422
    r = auth_client.post("/api/hosts", json={**HOST, "ip_mode": "block", "ip_list_ids": [99]})
    assert r.status_code == 422


def test_trusted_proxy_settings(auth_client: TestClient, caddy: FakeCaddy) -> None:
    cf = auth_client.post(
        "/api/ip-lists", json={"name": "Cloudflare", "entries": ["173.245.48.0/20"]}
    ).json()
    r = auth_client.put(
        "/api/settings/general",
        json={"trusted_proxies": ["10.0.0.1"], "trusted_proxy_list_ids": [cf["id"]]},
    )
    assert r.status_code == 200
    ranges = caddy.last["apps"]["http"]["servers"]["https"]["trusted_proxies"]["ranges"]
    assert ranges == ["10.0.0.1/32", "173.245.48.0/20"]
    assert "Vertrauenswürdige Proxys" in auth_client.get("/api/ip-lists").json()[0]["used_by"]
