from fastapi.testclient import TestClient

from tesseract.caddy.config import HostSpec, NodeSpec, build_config, waf_directives
from tests.conftest import FakeCaddy

HOST = {
    "domain": "git.example.org",
    "node_id": 1,
    "upstream_host": "10.0.0.5",
    "upstream_port": 3000,
}


def _handlers(caddy: FakeCaddy, domain: str) -> list[dict]:
    routes = caddy.last["apps"]["http"]["servers"]["https"]["routes"]
    route = next(r for r in routes if r["match"][0]["host"] == [domain])
    return [h for r in route["handle"][0]["routes"] for h in r["handle"]]


def test_directives() -> None:
    d = waf_directives("block", 3, [942100, 920350, 942100])
    assert "SecRuleEngine On" in d
    assert "blocking_paranoia_level=3" in d
    assert d.count("SecRuleRemoveById") == 2
    # Ausnahmen kommen nach dem Regelsatz, sonst wirken sie nicht
    assert d.index("Include @owasp_crs") < d.index("SecRuleRemoveById 920350")
    assert "SecRuleEngine DetectionOnly" in waf_directives("detect", 9, [])
    assert "blocking_paranoia_level=4" in waf_directives("detect", 9, [])


def test_waf_handler_order() -> None:
    host = HostSpec(1, "a.example.org", "http", "10.0.0.1", 80, waf_mode="block", access="mtls")
    cfg = build_config(NodeSpec(admin_listen="x", hosts=[host], client_ca_der_b64="AA=="))
    routes = cfg["apps"]["http"]["servers"]["https"]["routes"][0]["handle"][0]["routes"]
    # zuerst die Zertifikatsprüfung (billig), dann die WAF, zuletzt der Proxy
    assert routes[0]["handle"][0]["status_code"] == 403
    assert routes[1]["handle"][0]["handler"] == "waf"
    assert routes[-1]["handle"][0]["handler"] == "reverse_proxy"


def test_new_host_uses_default(auth_client: TestClient, caddy: FakeCaddy) -> None:
    host = auth_client.post("/api/hosts", json=HOST).json()["host"]
    assert host["waf_mode"] == "detect" and host["waf_paranoia"] == 1
    assert "waf" in [h["handler"] for h in _handlers(caddy, "git.example.org")]

    auth_client.put(
        "/api/settings/general",
        json={"waf_default_mode": "block", "waf_default_paranoia": 2},
    )
    other = auth_client.post("/api/hosts", json={**HOST, "domain": "wiki.example.org"}).json()
    assert other["host"]["waf_mode"] == "block" and other["host"]["waf_paranoia"] == 2


def test_update_keeps_waf_when_omitted(auth_client: TestClient, caddy: FakeCaddy) -> None:
    host = auth_client.post(
        "/api/hosts", json={**HOST, "waf_mode": "block", "waf_exclusions": [942100]}
    ).json()["host"]
    r = auth_client.put(f"/api/hosts/{host['id']}", json={**HOST, "upstream_port": 3001})
    assert r.json()["host"]["waf_mode"] == "block"
    # Ausnahmen werden aber mit dem Formular mitgeschickt – leer = keine
    assert r.json()["host"]["waf_exclusions"] == []

    r = auth_client.put(
        f"/api/hosts/{host['id']}",
        json={**HOST, "upstream_port": 3001, "waf_mode": "off", "waf_exclusions": [920350]},
    )
    assert "waf" not in [h["handler"] for h in _handlers(caddy, "git.example.org")]
    v = auth_client.get(f"/api/hosts/{host['id']}/versions").json()[0]
    assert {c["field"] for c in v["changes"]} == {"waf_mode", "waf_exclusions"}


def test_validation(auth_client: TestClient) -> None:
    for bad in ({"waf_mode": "loud"}, {"waf_paranoia": 5}, {"waf_exclusions": [0]}):
        assert auth_client.post("/api/hosts", json={**HOST, **bad}).status_code == 422, bad


def test_controller_waf(auth_client: TestClient, caddy: FakeCaddy) -> None:
    auth_client.put("/api/settings/general", json={"controller_waf_mode": "block"})
    routes = caddy.last["apps"]["http"]["servers"]["https"]["routes"]
    ctl = next(r for r in routes if r.get("@id") == "controller")
    handlers = [h["handler"] for r in ctl["handle"][0]["routes"] for h in r["handle"]]
    assert handlers == ["waf", "reverse_proxy"]
