import json

from tesseract.caddy.config import HostSpec, NodeSpec, build_config, is_public_name


def _host(**kw) -> HostSpec:
    base = dict(
        id=1,
        domain="musik.example.org",
        upstream_scheme="http",
        upstream_host="10.0.1.20",
        upstream_port=4533,
    )
    return HostSpec(**{**base, **kw})


def _servers(config: dict) -> dict:
    return config["apps"]["http"]["servers"]


def test_admin_listen_is_kept() -> None:
    cfg = build_config(NodeSpec(admin_listen="0.0.0.0:2019"))
    assert cfg["admin"] == {"listen": "0.0.0.0:2019"}


def test_host_route_and_redirect() -> None:
    cfg = build_config(NodeSpec(admin_listen="x", hosts=[_host()]))
    https, http = _servers(cfg)["https"], _servers(cfg)["http"]
    route = https["routes"][0]
    assert route["match"] == [{"host": ["musik.example.org"]}]
    proxy = route["handle"][0]["routes"][-1]["handle"][0]
    assert proxy == {"handler": "reverse_proxy", "upstreams": [{"dial": "10.0.1.20:4533"}]}
    assert http["routes"][0]["handle"][0]["status_code"] == 308


def test_no_force_https_serves_on_port_80() -> None:
    cfg = build_config(NodeSpec(admin_listen="x", hosts=[_host(force_https=False)]))
    http_route = _servers(cfg)["http"]["routes"][0]
    assert http_route["handle"][0]["handler"] == "subroute"


def test_options() -> None:
    cfg = build_config(
        NodeSpec(
            admin_listen="x",
            hosts=[_host(websockets=False, compression=True, upstream_scheme="https")],
        )
    )
    routes = _servers(cfg)["https"]["routes"][0]["handle"][0]["routes"]
    assert routes[0]["handle"][0]["status_code"] == 403  # WebSockets gesperrt
    assert routes[1]["handle"][0]["handler"] == "encode"
    assert routes[2]["handle"][0]["transport"] == {"protocol": "http", "tls": {}}


def test_controller_route_first_and_acme_policy() -> None:
    cfg = build_config(
        NodeSpec(
            admin_listen="x",
            hosts=[_host(), _host(id=2, domain="intern.localhost")],
            controller_domain="tesseract.example.org",
            controller_upstream="tesseract:8000",
            acme_email="admin@example.org",
        )
    )
    assert _servers(cfg)["https"]["routes"][0]["@id"] == "controller"
    policies = cfg["apps"]["tls"]["automation"]["policies"]
    # *.localhost bekommt ein Zertifikat aus Caddys eigener CA
    assert {"subjects": ["intern.localhost"], "issuers": [{"module": "internal"}]} in policies
    policy = next(p for p in policies if p["issuers"][0]["module"] == "acme")
    assert policy["subjects"] == ["tesseract.example.org", "musik.example.org"]
    assert policy["issuers"][0]["email"] == "admin@example.org"


def test_ipv6_upstream() -> None:
    cfg = build_config(NodeSpec(admin_listen="x", hosts=[_host(upstream_host="fd00::5")]))
    proxy = _servers(cfg)["https"]["routes"][0]["handle"][0]["routes"][-1]["handle"][0]
    assert proxy["upstreams"] == [{"dial": "[fd00::5]:4533"}]


def test_public_name() -> None:
    assert is_public_name("a.example.org")
    assert not is_public_name("localhost")
    assert not is_public_name("10.0.0.1")


def test_controller_only_from_admin_networks() -> None:
    spec = NodeSpec(
        admin_listen="x",
        controller_domain="tesseract.example.org",
        controller_upstream="tesseract:8000",
    )
    # Standard: keine Prüfung
    first = _servers(build_config(spec))["https"]["routes"][0]["handle"][0]["routes"][0]
    assert "abort" not in json.dumps(first)

    from dataclasses import replace

    spec = replace(spec, controller_networks=("192.168.178.0/24", "fd00::/8"))
    cfg = build_config(spec)
    gate = _servers(cfg)["https"]["routes"][0]["handle"][0]["routes"][0]
    nots = gate["match"][0]["not"]
    assert nots[0] == {"remote_ip": {"ranges": ["192.168.178.0/24", "fd00::/8"]}}
    # Einladungen und Agents bleiben von überall erreichbar
    assert "/e/*" in nots[1]["path"] and "/api/agent/*" in nots[1]["path"]
    assert any(h.get("abort") for h in gate["handle"])
    # auch die HTTP-Umleitung bricht von außen ab
    http = next(
        r
        for r in _servers(cfg)["http"]["routes"]
        if r["match"][0]["host"] == ["tesseract.example.org"]
    )
    assert http["handle"][0]["routes"][0]["match"] == gate["match"]


def test_admin_networks_setting() -> None:
    import pytest

    from tesseract.config import Settings

    s = Settings(admin_networks="0.0.0.0/0, ::/0")
    assert s.admin_networks_open
    s = Settings(admin_networks="192.168.178.5/24;10.8.0.0/24")
    assert s.admin_network_list == ["192.168.178.0/24", "10.8.0.0/24"]
    assert not s.admin_networks_open
    assert not Settings(admin_networks="0.0.0.0/0").admin_networks_open  # IPv6 dann gesperrt
    with pytest.raises(ValueError, match="kein Netz"):
        Settings(admin_networks="192.168.178.0/24, intern")


def test_agent_api_can_be_restricted_too() -> None:
    from dataclasses import replace

    spec = NodeSpec(
        admin_listen="x",
        controller_domain="tesseract.example.org",
        controller_upstream="tesseract:8000",
        controller_networks=("192.168.178.0/24",),
    )
    paths = _servers(build_config(spec))["https"]["routes"][0]["handle"][0]["routes"][0]["match"][
        0
    ]["not"][1]["path"]
    assert "/api/agent/*" in paths and "/install/*" in paths and "/e/*" in paths
    spec = replace(spec, controller_agents_open=False)
    paths = _servers(build_config(spec))["https"]["routes"][0]["handle"][0]["routes"][0]["match"][
        0
    ]["not"][1]["path"]
    assert "/api/agent/*" not in paths and "/install/*" not in paths
    # Gäste (Einladung, Verlängern) bleiben erreichbar
    assert "/e/*" in paths and "/v" in paths


def test_cert_users_pass_admin_networks() -> None:
    """Personen mit Zugriff per Gerätezertifikat erreichen die Oberfläche auch von unterwegs."""
    from dataclasses import replace

    from tesseract.caddy.config import FINGERPRINT

    spec = NodeSpec(
        admin_listen="x",
        controller_domain="tesseract.example.org",
        controller_upstream="tesseract:8000",
        controller_networks=("192.168.178.0/24",),
    )
    gate = _servers(build_config(spec))["https"]["routes"][0]["handle"][0]["routes"][0]
    assert len(gate["match"][0]["not"]) == 2  # ohne Personen: keine Ausnahme

    fp = "ab" * 32
    spec = replace(spec, controller_cert_users=(fp,))
    gate = _servers(build_config(spec))["https"]["routes"][0]["handle"][0]["routes"][0]
    assert gate["match"][0]["not"][2] == {"vars": {FINGERPRINT: [fp]}}


def test_cert_users_get_https_redirect_on_port_80() -> None:
    """Über HTTP gibt es kein Zertifikat – mit Zertifikats-Personen leitet Port 80 immer um."""
    from dataclasses import replace

    spec = NodeSpec(
        admin_listen="x",
        controller_domain="tesseract.example.org",
        controller_upstream="tesseract:8000",
        controller_networks=("192.168.178.0/24",),
    )

    def port80(s: NodeSpec) -> str:
        routes = _servers(build_config(s))["http"]["routes"]
        r = next(r for r in routes if r["match"][0]["host"] == ["tesseract.example.org"])
        return json.dumps(r)

    assert '"abort": true' in port80(spec)  # ohne Personen: von außen keine Antwort
    with_users = port80(replace(spec, controller_cert_users=("ab" * 32,)))
    assert '"abort": true' not in with_users and '"status_code": 308' in with_users
    # HTTPS bricht für Fremde ohne Zertifikat weiter ab
    https = _servers(build_config(replace(spec, controller_cert_users=("ab" * 32,))))["https"]
    assert '"abort": true' in json.dumps(https["routes"][0])
