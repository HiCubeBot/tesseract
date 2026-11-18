from fastapi.testclient import TestClient

from tesseract.caddy.config import HostSpec, NodeSpec, build_config, covering_wildcard
from tests.conftest import FakeCaddy

TOKEN = "abcdefghijABCDEFGHIJ0123456789abcdefghij"


def test_covering() -> None:
    w = ("*.home.example.org",)
    assert covering_wildcard("grafana.home.example.org", w) == "*.home.example.org"
    assert covering_wildcard("a.b.home.example.org", w) is None  # nur eine Ebene
    assert covering_wildcard("home.example.org", w) is None
    assert covering_wildcard("*.home.example.org", w) == "*.home.example.org"


def test_config() -> None:
    hosts = [
        HostSpec(1, "grafana.home.example.org", "http", "10.0.0.1", 3000),
        HostSpec(2, "nas.home.example.org", "http", "10.0.0.2", 5000),
        HostSpec(3, "blog.example.org", "http", "10.0.0.3", 80),
    ]
    cfg = build_config(
        NodeSpec(
            admin_listen="x",
            hosts=hosts,
            acme_email="a@example.org",
            cloudflare_token=TOKEN,
            wildcard_certs=("*.home.example.org",),
        )
    )
    tls = cfg["apps"]["tls"]
    assert tls["certificates"] == {"automate": ["*.home.example.org"]}
    policies = {tuple(p["subjects"]): p for p in tls["automation"]["policies"]}
    assert ("*.home.example.org",) in policies  # DNS-01
    assert ("blog.example.org",) in policies  # HTTP-01, eigenes Zertifikat
    skip = cfg["apps"]["http"]["servers"]["https"]["automatic_https"]["skip_certificates"]
    assert skip == ["grafana.home.example.org", "nas.home.example.org"]

    # Ohne Token: kein Wildcard, jeder Host wie gehabt
    cfg = build_config(
        NodeSpec(admin_listen="x", hosts=hosts, wildcard_certs=("*.home.example.org",))
    )
    assert "skip_certificates" not in cfg["apps"]["http"]["servers"]["https"]["automatic_https"]


def test_api(auth_client: TestClient, caddy: FakeCaddy) -> None:
    r = auth_client.put("/api/settings/general", json={"wildcard_certs": ["home.example.org"]})
    assert r.status_code == 409  # Token fehlt
    r = auth_client.put(
        "/api/settings/general",
        json={
            "cloudflare_token": TOKEN,
            "wildcard_certs": ["home.example.org", "*.HOME.example.org"],
        },
    )
    assert r.json()["wildcard_certs"] == ["*.home.example.org"]

    host = auth_client.post(
        "/api/hosts",
        json={
            "domain": "grafana.home.example.org",
            "node_id": 1,
            "upstream_host": "10.0.0.5",
            "upstream_port": 3000,
        },
    ).json()["host"]
    assert host["wildcard_cert"] == "*.home.example.org"
    assert caddy.last["apps"]["tls"]["certificates"]["automate"] == ["*.home.example.org"]

    # Intern + öffentlicher Name geht ohne eigenes DNS-01, wenn ein Wildcard ihn abdeckt
    auth_client.put("/api/settings/general", json={"internal_networks": ["192.168.0.0/16"]})
    r = auth_client.post(
        "/api/hosts",
        json={
            "domain": "nas.home.example.org",
            "node_id": 1,
            "upstream_host": "10.0.0.6",
            "upstream_port": 5000,
            "internal": True,
        },
    )
    assert r.status_code == 201, r.text
