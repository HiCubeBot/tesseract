"""Phase 5: Prometheus-Endpunkt."""

import json

import httpx
from fastapi.testclient import TestClient

from tesseract.caddy.config import FINGERPRINT_HEADER
from tesseract.metrics import Metrics, relabel_caddy
from tests.conftest import FakeCaddy
from tests.test_logs import SQLI_URI, WAF_VIOLATION, WAF_WARNING, _local_ingest, access
from tests.test_nodes_agent import _joined

CADDY_TEXT = (
    "# HELP caddy_http_requests_total Counter of HTTP(S) requests made.\n"
    "# TYPE caddy_http_requests_total counter\n"
    'caddy_http_requests_total{handler="reverse_proxy",server="https"} 7\n'
    "# TYPE caddy_config_last_reload_successful gauge\n"
    "caddy_config_last_reload_successful 1\n"
    "go_goroutines 12\n"
)


def _enable(c: TestClient, **kw) -> dict:
    r = c.put("/api/settings/observability", json={"metrics_enabled": True, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_relabel_groups_families() -> None:
    families: dict = {}
    relabel_caddy(CADDY_TEXT, "local", families)
    relabel_caddy(CADDY_TEXT, "pi", families)
    fam = families["caddy_http_requests_total"]
    assert len(fam["meta"]) == 2  # HELP + TYPE nur einmal
    assert fam["values"] == [
        'caddy_http_requests_total{node="local",handler="reverse_proxy",server="https"} 7',
        'caddy_http_requests_total{node="pi",handler="reverse_proxy",server="https"} 7',
    ]
    assert families["caddy_config_last_reload_successful"]["values"][0].startswith(
        'caddy_config_last_reload_successful{node="local"} 1'
    )
    assert not any("go_goroutines" in v for f in families.values() for v in f["values"])


def test_histogram() -> None:
    m = Metrics()
    m.observe("local", "git", 200, "ok", 30.0, 10)
    m.observe("local", "git", 403, "waf", 1.0, 0)
    text = "\n".join(m.render_counters())
    assert 'tesseract_request_duration_seconds_bucket{node="local",host="git",le="0.025"} 0' in text
    assert 'tesseract_request_duration_seconds_bucket{node="local",host="git",le="0.05"} 1' in text
    assert 'tesseract_requests_total{node="local",host="git",status="4xx",reason="waf"} 1' in text
    assert 'tesseract_waf_blocked_total{node="local",host="git"} 1' in text


def test_metrics_endpoint_token(auth_client: TestClient, caddy: FakeCaddy) -> None:
    assert auth_client.get("/metrics").status_code == 404  # aus
    cfg = _enable(auth_client)
    assert cfg["metrics_url"] == "https://tesseract.example.org/metrics"
    assert auth_client.get("/metrics").status_code == 401
    token = auth_client.post("/api/settings/observability/token").json()["token"]
    assert auth_client.get("/api/settings/observability").json()["metrics_token_set"] is True
    bad = auth_client.get("/metrics", headers={"Authorization": "Bearer falsch"})
    assert bad.status_code == 401

    _local_ingest(
        auth_client,
        [access(), access(SQLI_URI, status=403, ip="198.51.100.140")],
        [WAF_WARNING, WAF_VIOLATION],
    )
    original = caddy.handler

    def with_metrics(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/metrics":
            return httpx.Response(200, text=CADDY_TEXT)
        return original(request)

    auth_client.app.state.caddy_transport = httpx.MockTransport(with_metrics)
    r = auth_client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    text = r.text
    assert 'tesseract_node_up{node="local",kind="local"} 1' in text
    assert (
        'tesseract_requests_total{node="local",host="git.example.org",status="2xx",reason="ok"} 1'
        in text
    )
    assert 'tesseract_waf_blocked_total{node="local",host="git.example.org"} 1' in text
    assert (
        'caddy_http_requests_total{node="local",handler="reverse_proxy",server="https"} 7' in text
    )
    assert "go_goroutines" not in text
    # ohne Caddy-Metriken
    _enable(auth_client, metrics_caddy=False)
    text = auth_client.get("/metrics", headers={"Authorization": f"Bearer {token}"}).text
    assert "caddy_http_requests_total" not in text
    assert auth_client.get("/api/settings/observability").json()["last_scrape"]


def test_metrics_ip_and_mtls(auth_client: TestClient) -> None:
    r = auth_client.put(
        "/api/settings/observability", json={"metrics_enabled": True, "metrics_auth": "ip"}
    )
    assert r.status_code == 422
    _enable(auth_client, metrics_auth="ip", metrics_networks=["10.0.0.0/8"])
    assert auth_client.get("/metrics", headers={"X-Forwarded-For": "10.1.2.3"}).status_code == 200
    assert auth_client.get("/metrics", headers={"X-Forwarded-For": "192.0.2.1"}).status_code == 401
    _enable(auth_client, metrics_auth="mtls")
    assert auth_client.get("/metrics", headers={FINGERPRINT_HEADER: "ab" * 32}).status_code == 401


def test_agent_caddy_metrics(auth_client: TestClient) -> None:
    agent, _ = _joined(auth_client)
    r = agent.post("/api/agent/status", {"caddy_metrics": CADDY_TEXT})
    assert r.json()["caddy_metrics"] is False  # Metriken aus → nicht gewünscht
    _enable(auth_client, metrics_auth="ip", metrics_networks=["10.0.0.0/8"])
    r = agent.post("/api/agent/status", {"caddy_metrics": CADDY_TEXT})
    assert r.json()["caddy_metrics"] is True
    text = auth_client.get("/metrics", headers={"X-Forwarded-For": "10.0.0.1"}).text
    assert 'caddy_http_requests_total{node="pi-eltern",' in text


def test_grafana(auth_client: TestClient) -> None:
    r = auth_client.get("/api/settings/observability/grafana.json")
    d = json.loads(r.content)
    assert d["uid"] == "tesseract" and len(d["panels"]) >= 8
