from fastapi.testclient import TestClient

from tesseract.caddy.config import HostSpec, NodeSpec, build_config, redact
from tests.conftest import FakeCaddy

HOST = {
    "domain": "*.home.example.org",
    "node_id": 1,
    "upstream_host": "10.0.0.5",
    "upstream_port": 80,
}
TOKEN = "cf-test-token-123"


def test_policies_and_route_order() -> None:
    hosts = [
        HostSpec(1, "*.home.example.org", "http", "10.0.0.1", 80, tls_challenge="dns"),
        HostSpec(2, "nas.home.example.org", "http", "10.0.0.2", 80),
    ]
    cfg = build_config(
        NodeSpec(admin_listen="x", hosts=hosts, acme_email="a@example.org", cloudflare_token=TOKEN)
    )
    routes = cfg["apps"]["http"]["servers"]["https"]["routes"]
    # konkreter Name vor dem Wildcard
    assert [r["match"][0]["host"][0] for r in routes] == [
        "nas.home.example.org",
        "*.home.example.org",
    ]
    dns, http = cfg["apps"]["tls"]["automation"]["policies"]
    assert dns["subjects"] == ["*.home.example.org"]
    provider = dns["issuers"][0]["challenges"]["dns"]["provider"]
    assert provider == {"name": "cloudflare", "api_token": TOKEN}
    assert http["subjects"] == ["nas.home.example.org"] and "challenges" not in http["issuers"][0]

    shown = redact(cfg)
    assert TOKEN not in str(shown) and TOKEN in str(cfg)


def test_api(auth_client: TestClient, caddy: FakeCaddy) -> None:
    # Wildcard nur mit DNS-01
    assert auth_client.post("/api/hosts", json=HOST).status_code == 422
    # DNS-01 nur mit Token
    r = auth_client.post("/api/hosts", json={**HOST, "tls_challenge": "dns"})
    assert r.status_code == 409

    r = auth_client.put("/api/settings/general", json={"cloudflare_token": TOKEN})
    assert r.json()["cloudflare_token_set"] is True
    assert TOKEN not in r.text
    host = auth_client.post("/api/hosts", json={**HOST, "tls_challenge": "dns"})
    assert host.status_code == 201, host.text

    policy = caddy.last["apps"]["tls"]["automation"]["policies"][0]
    assert policy["issuers"][0]["challenges"]["dns"]["provider"]["api_token"] == TOKEN
    # Anzeige im UI ohne Token
    assert TOKEN not in auth_client.get("/api/nodes/1/config").text
    # Audit-Log ohne Token und ohne verschlüsselten Wert
    audit = auth_client.get("/api/audit?q=settings").json()[0]
    assert audit["details"]["cloudflare_token"] == "geändert"

    # Weglassen = unverändert, leer = löschen (nicht solange Hosts DNS-01 nutzen)
    assert auth_client.put("/api/settings/general", json={}).json()["cloudflare_token_set"]
    assert (
        auth_client.put("/api/settings/general", json={"cloudflare_token": ""}).status_code == 409
    )
