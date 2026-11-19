"""Loki als zusätzlicher Log-Speicher."""

import json

import httpx
from fastapi.testclient import TestClient

from tesseract.loki import LokiShipper, flush, payload, push_url
from tests.test_logs import SQLI_URI, WAF_SCORE, WAF_VIOLATION, WAF_WARNING, _local_ingest, access


class FakeLoki:
    def __init__(self) -> None:
        self.pushes: list[dict] = []
        self.headers: list[httpx.Headers] = []
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("verbindung abgelehnt")
        assert request.url.path == "/loki/api/v1/push"
        self.pushes.append(json.loads(request.content))
        self.headers.append(request.headers)
        return httpx.Response(204)


def test_push_url() -> None:
    assert push_url("http://loki:3100") == "http://loki:3100/loki/api/v1/push"
    assert push_url("http://loki:3100/loki/api/v1/push/") == "http://loki:3100/loki/api/v1/push"


def test_shipper_queue_limits() -> None:
    s = LokiShipper(max_queue=3)
    s.add({"x": 0})
    assert not s.queue  # aus, solange keine URL eingestellt ist
    s.enabled = True
    for i in range(5):
        s.add({"x": i})
    assert [e["x"] for e in s.queue] == [2, 3, 4] and s.dropped == 2
    batch = s.take(2)
    s.add({"x": 5})
    s.requeue(batch)  # nur noch Platz für einen
    assert [e["x"] for e in s.queue] == [3, 4, 5] and s.dropped == 3


def test_ingest_ships_to_loki(auth_client: TestClient) -> None:
    loki = FakeLoki()
    app = auth_client.app
    app.state.loki_transport = httpx.MockTransport(loki.handler)
    r = auth_client.put(
        "/api/settings/observability",
        json={"loki_url": "http://loki:3100/", "loki_tenant": "homelab"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["loki_url"] == "http://loki:3100"
    _local_ingest(
        auth_client,
        [access(), access(SQLI_URI, status=403, ip="198.51.100.140")],
        [WAF_WARNING, WAF_SCORE, WAF_VIOLATION],
    )
    shipper = app.state.logs.loki
    assert len(shipper.queue) == 2
    assert flush(shipper, "http://loki:3100", "homelab", app.state.loki_transport)
    assert loki.headers[0]["X-Scope-OrgID"] == "homelab"
    streams = {s["stream"]["reason"]: s for s in loki.pushes[0]["streams"]}
    assert streams["waf"]["stream"] == {
        "job": "tesseract",
        "node": "local",
        "host": "git.example.org",
        "reason": "waf",
    }
    line = json.loads(streams["waf"]["values"][0][1])
    assert line["waf_rules"] == [942100] and line["status"] == 403 and line["ip"]
    assert "device" not in line  # leere Felder fallen weg

    status = auth_client.get("/api/settings/observability").json()["loki"]
    assert status["pushed"] == 2 and status["queued"] == 0 and status["last_error"] is None


def test_loki_down_keeps_entries(auth_client: TestClient) -> None:
    loki = FakeLoki()
    loki.down = True
    s = LokiShipper()
    s.enabled = True
    from tesseract.db.models import utcnow

    s.add({"ts": utcnow(), "node": "local", "host": "a", "reason": "ok", "status": 200})
    assert not flush(s, "http://loki:3100", transport=httpx.MockTransport(loki.handler))
    assert len(s.queue) == 1 and "verbindung abgelehnt" in s.last_error
    loki.down = False
    assert flush(s, "http://loki:3100", transport=httpx.MockTransport(loki.handler))
    assert not s.queue and s.last_error is None


def test_loki_settings_and_test(auth_client: TestClient) -> None:
    loki = FakeLoki()
    auth_client.app.state.loki_transport = httpx.MockTransport(loki.handler)
    r = auth_client.put("/api/settings/observability", json={"loki_url": "loki:3100"})
    assert r.status_code == 422
    r = auth_client.post(
        "/api/settings/observability/loki-test", json={"loki_url": "http://loki:3100"}
    )
    assert r.json() == {"ok": True, "error": None}
    assert loki.pushes[0]["streams"][0]["stream"]["reason"] == "test"
    loki.down = True
    r = auth_client.post(
        "/api/settings/observability/loki-test", json={"loki_url": "http://loki:3100"}
    )
    assert r.json()["ok"] is False


def test_payload_sorted() -> None:
    from datetime import UTC, datetime

    a = {"ts": datetime(2026, 1, 1, 0, 0, 2, tzinfo=UTC), "node": "n", "host": "", "reason": "ok"}
    b = {**a, "ts": datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)}
    s = payload([a, b])["streams"][0]
    assert s["stream"]["host"] == "-" and s["values"][0][0] < s["values"][1][0]
