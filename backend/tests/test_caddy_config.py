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
