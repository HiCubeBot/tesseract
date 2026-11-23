"""Statistik pro Host, Aktivität in der Hostliste und die SQLite-Abfrageschicht."""

from datetime import timedelta

from fastapi.testclient import TestClient

from tesseract.db.models import utcnow
from tesseract.hoststats import path_key
from tesseract.logs import parse_access
from tesseract.logstore import Sel
from tesseract.sqlstore import SqlStore
from tests.test_stats import _add

ROWS = [
    {"uri": "/api/today?x=1", "user_agent": "Mozilla/5.0", "encoding": "gzip", "bytes_in": 50},
    {"uri": "/api/today", "user_agent": "Mozilla/5.0", "ip": "192.0.2.11", "encoding": "gzip"},
    {"uri": "/icons/a.png", "user_agent": "Googlebot/2.1", "ip": "192.0.2.12"},
    {"uri": "/api/items/12345", "status": 502, "duration_ms": 90.0, "user_agent": "Mozilla/5.0"},
    {"uri": "/login", "status": 403, "reason": "waf", "ip": "198.51.100.1", "country": "NL"},
    {"uri": "/", "status": 200, "country": "DE", "ago": 60 * 30},  # vor 30 Stunden
    {"uri": "/", "host": "andere.example.org"},
    {"uri": "/", "ago": 60 * 24 + 30},  # gestern → Vorzeitraum bei 24 h
]


def test_path_key() -> None:
    assert path_key("/api/today?x=1") == "/api/today"
    assert path_key("/api/items/12345/edit") == "/api/items/*/edit"
    assert path_key("/icons/logo-192.PNG") == "/icons/*.png"
    assert path_key("/u/3f2a9c4e-1b2c-4d5e-8f90-0a1b2c3d4e5f") == "/u/*"
    assert path_key("") == "/"


def test_parse_access_new_fields() -> None:
    line = (
        '{"msg":"handled request","ts":1700000000.5,"status":200,"size":10,"bytes_read":42,'
        '"duration":0.01,"resp_headers":{"Content-Encoding":["zstd"]},'
        '"request":{"client_ip":"192.0.2.1","host":"a.example.org","proto":"HTTP/2.0",'
        '"method":"GET","uri":"/"}}'
    )
    p = parse_access(line)
    assert p["bytes_in"] == 42 and p["proto"] == "2" and p["encoding"] == "zstd"


def test_host_stats(auth_client: TestClient) -> None:
    _add(auth_client, [dict(r) for r in ROWS])
    r = auth_client.get("/api/stats/host", params={"domain": "git.example.org"})
    assert r.status_code == 200
    d = r.json()
    assert d["source"] == "sqlite"
    assert d["requests"]["total"] == 5 and d["requests"]["previous"] == 2
    # verschiedene IPs ohne Bot, nur durchgelassen: .10 und .11
    assert d["visitors"]["total"] == 2
    assert d["bytes"]["in"] == 50
    assert d["errors"]["count"] == 1
    assert d["compression"]["share"] == 66.7 and d["compression"]["encodings"] == ["gzip"]
    hourly = d["hourly"]
    assert len(hourly) in (24, 25) and hourly[0]["t"].endswith(":00:00Z")
    assert sum(h["requests"] for h in hourly) == 5 and sum(h["previous"] for h in hourly) == 2
    assert d["denied"] == 1 and sum(h.get("waf", 0) for h in hourly) == 1
    paths = {p["path"]: p for p in d["paths"]}
    assert paths["/api/today"]["count"] == 2
    assert paths["/api/items/*"]["errors"] == 1 and paths["/login"]["denied"] == 1
    assert d["top_denied_ips"][0] == {
        "ip": "198.51.100.1",
        "count": 1,
        "reason": "waf",
        "country": "NL",
    }
    assert {c["country"] for c in d["countries"]} == {"NL"}
    week = auth_client.get(
        "/api/stats/host", params={"domain": "git.example.org", "range": "7d"}
    ).json()
    assert week["requests"]["total"] == 7 and len(week["hourly"]) in (168, 169)


def test_activity(auth_client: TestClient) -> None:
    _add(auth_client, [dict(r) for r in ROWS])
    d = auth_client.get("/api/stats/activity").json()
    git = d["hosts"]["git.example.org"]
    assert git["total"] == 5 and len(git["hourly"]) in (24, 25)
    assert d["hosts"]["andere.example.org"]["total"] == 1


def test_sqlstore_ops(auth_client: TestClient) -> None:
    _add(auth_client, [dict(r) for r in ROWS])
    with auth_client.app.state.db.sessionmaker() as db:
        s = SqlStore(db)
        end = utcnow()
        start = end - timedelta(hours=2)
        assert s.count(Sel().add("ip", "cidr", "198.51.100.0/24"), start, end)[0][2] == 1
        assert s.count(Sel().add("waf_rules", "rule", 942100), start, end) == []
        bots = Sel().add("user_agent", "ire", "bot")
        assert s.count(bots, start, end)[0][2] == 1
        by_node = s.count(Sel().add("node", "eq", "local"), start, end, ["node"])
        assert by_node[0][0] == ("local",)
        q = s.quantile(0.5, Sel().add("reason", "eq", "ok"), start, end, "duration_ms")
        assert q[0][2] == 10.0


def test_not_contains_condition() -> None:
    from tesseract.logstore import Cond, LokiStore, VictoriaLogsStore

    c = Cond("user_agent", "nire", "bot")
    assert LokiStore("http://l")._cond(c) == 'user_agent!~"(?i).*bot.*"'
    assert VictoriaLogsStore("http://v")._cond(c) == '-user_agent:~"(?i)bot"'
