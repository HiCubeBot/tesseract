"""Logs und Statistik aus Loki / VictoriaLogs (Abfragen gebaut, Antworten ausgewertet)."""

import json
from datetime import UTC, datetime, timedelta

import httpx
from fastapi.testclient import TestClient

from tesseract.logstore import (
    LokiStore,
    Sel,
    VictoriaLogsStore,
    from_id,
    sel_from_query,
    to_id,
)

T = datetime(2026, 11, 20, 10, 0, 0, 123456, tzinfo=UTC)
LINE = {
    "method": "GET",
    "uri": "/login",
    "status": 403,
    "duration_ms": 1.5,
    "size": 10,
    "ip": "198.51.100.1",
    "waf_rules": [942100],
    "device": "Laptop",
    "person": "Anna",
}


def test_ids_roundtrip() -> None:
    assert from_id(to_id(T)) == T
    assert to_id(T) < 2**53  # passt verlustfrei in JavaScript


def test_loki_query() -> None:
    s = LokiStore("http://loki:3100/loki/api/v1/push")
    sel = sel_from_query("host:git status:4xx ip:198.51.100.0/24 rule:942100 login", "waf")
    q = s._pipeline(sel)
    assert q.startswith('{job="tesseract", reason=~"waf"}')
    assert r'|~ "\"waf_rules\":\\[[^\\]]*\\b942100\\b"' in q
    assert '| json ip="ip", status="status", uri="uri"' in q
    assert 'host=~"git(\\\\..*)?"' in q
    assert "status>=400 | status<500" in q
    assert 'ip=ip("198.51.100.0/24")' in q
    assert 'uri=~"(?i).*login.*" or host=~"(?i).*login.*"' in q
    assert s.base == "http://loki:3100"


def test_victorialogs_query() -> None:
    s = VictoriaLogsStore("http://vl:9428/insert/jsonline")
    sel = sel_from_query("status:403 country:de", "denied")
    f = s._filter(sel, T - timedelta(hours=1), T)
    assert f.startswith(
        '_time:[2026-11-20T09:00:00.123456Z, 2026-11-20T10:00:00.123456Z) {job="tesseract"}'
    )
    assert 'status:="403"' in f and 'country:="DE"' in f
    assert '(-reason:="ok" or status:>=400)' in f
    assert s.base == "http://vl:9428"


def test_loki_entries_and_counts() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/query_range") and "count_over_time" not in str(request.url):
            ns = str(int(T.timestamp() * 1e9))
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "result": [
                            {
                                "stream": {
                                    "job": "tesseract",
                                    "node": "local",
                                    "host": "git.example.org",
                                    "reason": "waf",
                                },
                                "values": [[ns, json.dumps(LINE)], [ns, json.dumps(LINE)]],
                            }
                        ]
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"result": [{"metric": {"reason": "waf"}, "value": [T.timestamp(), "7"]}]},
            },
        )

    s = LokiStore("http://loki:3100", "mandant", httpx.MockTransport(handler))
    out = s.entries(Sel(), T - timedelta(days=1), T, 10)
    assert [e["host"] for e in out] == ["git.example.org"] * 2
    # gleiche Mikrosekunde → eindeutige, absteigende IDs
    assert out[0]["id"] == to_id(T) and out[1]["id"] == to_id(T) - 1
    assert out[0]["waf_rules"] == [942100] and out[0]["person"] == "Anna"
    assert calls[0].headers["X-Scope-OrgID"] == "mandant"
    rows = s.count(Sel(), T - timedelta(days=1), T, ["reason"])
    assert rows == [(("waf",), None, 7.0)]
    assert "sum by (reason) (count_over_time(" in calls[-1].url.params["query"]
    assert "[86400s]" in calls[-1].url.params["query"]


def test_victorialogs_stats() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        q = dict(httpx.QueryParams(request.content.decode()))["query"]
        assert request.headers["AccountID"] == "3"
        if "| stats" in q:
            assert "| stats by (_time:3600s, reason) count() as v" in q
            return httpx.Response(
                200, text='{"_time":"2026-11-20T09:00:00Z","reason":"waf","v":"4"}\n'
            )
        return httpx.Response(
            200,
            text=json.dumps(
                {
                    "_time": "2026-11-20T10:00:00.123456789Z",
                    "node": "local",
                    "host": "-",
                    "reason": "ok",
                    **LINE,
                }
            )
            + "\n",
        )

    s = VictoriaLogsStore("http://vl:9428", "3", httpx.MockTransport(handler))
    rows = s.count(Sel(), T - timedelta(days=1), T, ["reason"], timedelta(hours=1))
    assert rows == [(("waf",), datetime(2026, 11, 20, 9, tzinfo=UTC), 4.0)]
    e = s.entries(Sel(), T - timedelta(days=1), T, 5)[0]
    assert e["ts"] == T and e["host"] == "" and e["status"] == 403


def test_api_reads_external(auth_client: TestClient) -> None:
    ns = str(int(T.timestamp() * 1e9))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/push"):
            return httpx.Response(204)
        q = request.url.params.get("query", "")
        if "count_over_time" in q:
            return httpx.Response(200, json={"status": "success", "data": {"result": []}})
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "result": [
                        {
                            "stream": {"node": "local", "host": "git.example.org", "reason": "waf"},
                            "values": [[ns, json.dumps(LINE)]],
                        }
                    ]
                },
            },
        )

    auth_client.app.state.loki_transport = httpx.MockTransport(handler)
    r = auth_client.put("/api/settings/observability", json={"logs_external": True})
    assert r.status_code == 422  # ohne URL nicht möglich
    r = auth_client.put(
        "/api/settings/observability", json={"loki_url": "http://loki:3100", "logs_external": True}
    )
    assert r.json()["logs_external"] is True
    page = auth_client.get("/api/logs").json()
    assert page["store"] == "loki" and page["entries"][0]["id"] == to_id(T)
    assert page["entries"][0]["host"] == "git.example.org"
    detail = auth_client.get(f"/api/logs/{to_id(T)}").json()
    assert detail["waf_rules"] == [942100] and detail["ip_requests"] == 0
    sec = auth_client.get("/api/stats/security").json()
    assert sec["source"] == "external" and sec["total"] == 0
    assert auth_client.get("/api/logs", params={"q": 'host:"x'}).status_code == 422


def test_external_countries_filter() -> None:
    from tesseract import stats_external

    seen = []

    class Store:
        def count(self, sel, start, end, by=(), step=None):
            seen.append([(c.field, c.op, c.value) for c in sel.conds])
            return [(("DE",), None, 5.0), (("",), None, 2.0), (("RU",), None, 5.0)]

    out = stats_external.countries(Store(), "24h", None, "allowed")
    assert out["countries"] == [{"country": "DE", "count": 5}, {"country": "RU", "count": 5}]
    assert out["unknown"] == 2
    assert ("reason", "eq", "ok") in seen[-1]
    stats_external.countries(Store(), "24h", "pi", "denied")
    assert ("node", "eq", "pi") in seen[-1] and any(
        f == "reason" and op == "in" for f, op, _ in seen[-1]
    )
