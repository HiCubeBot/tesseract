from fastapi.testclient import TestClient

from tesseract.caddy.config import HostSpec, NodeSpec, build_config
from tests.conftest import FakeCaddy

HOST = {
    "domain": "grafana.lan",
    "node_id": 1,
    "upstream_host": "10.0.0.5",
    "upstream_port": 3000,
    "internal": True,
}
NETS = ("192.168.178.0/24", "10.8.0.0/24")


def _servers(cfg: dict) -> dict:
    return cfg["apps"]["http"]["servers"]


def test_abort_first_and_on_port_80() -> None:
    host = HostSpec(
        1, "grafana.home.example.org", "http", "10.0.0.5", 3000, internal=True, waf_mode="block"
    )
    cfg = build_config(NodeSpec(admin_listen="x", hosts=[host], internal_networks=NETS))
    first = _servers(cfg)["https"]["routes"][0]["handle"][0]["routes"][0]
    assert first["match"] == [{"not": [{"remote_ip": {"ranges": list(NETS)}}]}]
    assert first["handle"] == [{"handler": "static_response", "abort": True}]
    http = _servers(cfg)["http"]["routes"][0]["handle"][0]["routes"]
    assert http[0]["handle"][0]["abort"] is True
    assert http[1]["handle"][0]["status_code"] == 308


def test_api(auth_client: TestClient, caddy: FakeCaddy) -> None:
    # ohne interne Netze nicht möglich
    assert auth_client.post("/api/hosts", json=HOST).status_code == 409
    r = auth_client.put("/api/settings/general", json={"internal_networks": list(NETS)})
    assert r.json()["internal_networks"] == list(NETS)

    # öffentlicher Name mit HTTP-01 geht nicht (von außen nicht erreichbar)
    r = auth_client.post("/api/hosts", json={**HOST, "domain": "grafana.example.org"})
    assert r.status_code == 409 and "DNS-01" in r.json()["detail"]

    # lokaler Name: Caddy nimmt sein eigenes Zertifikat
    host = auth_client.post("/api/hosts", json=HOST).json()["host"]
    assert host["internal"] is True
    routes = _servers(caddy.last)["https"]["routes"]
    route = next(r for r in routes if r["match"][0]["host"] == ["grafana.lan"])
    assert route["handle"][0]["routes"][0]["handle"][0]["abort"] is True

    # interne Netze lassen sich nicht leeren, solange sie benutzt werden
    r = auth_client.put("/api/settings/general", json={"internal_networks": []})
    assert r.status_code == 409


def test_internal_list(auth_client: TestClient, caddy: FakeCaddy) -> None:
    lst = auth_client.post("/api/ip-lists", json={"name": "VPN", "entries": ["10.8.0.0/24"]}).json()
    auth_client.put("/api/settings/general", json={"internal_list_ids": [lst["id"]]})
    auth_client.post("/api/hosts", json=HOST)
    route = next(
        r
        for r in _servers(caddy.last)["https"]["routes"]
        if r["match"][0]["host"] == ["grafana.lan"]
    )
    first = route["handle"][0]["routes"][0]
    assert first["match"][0]["not"][0]["remote_ip"]["ranges"] == ["10.8.0.0/24"]
    assert "Interne Netze" in auth_client.get("/api/ip-lists").json()[0]["used_by"]
