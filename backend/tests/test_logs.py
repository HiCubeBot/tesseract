"""Phase 5: Zentrale Logs – Parser, WAF-Zuordnung, Suche, Aktionen."""

import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from tesseract.caddy.config import NodeSpec, build_config
from tesseract.db.models import LogEntry, Node
from tesseract.logs import Collector, WafTracker, parse_access
from tests.conftest import FakeCaddy
from tests.test_hosts import HOST
from tests.test_nodes_agent import _joined

# Zeilen wie vom echten Caddy 2.11 mit coraza-caddy (gekürzt)
TS = 1795026076.95
SQLI_URI = "/search?q=1%27+OR+%271%27=%271"
WAF_WARNING = json.dumps(
    {
        "level": "error",
        "ts": TS,
        "logger": "http.handlers.waf",
        "msg": '[client "198.51.100.140"] Coraza: Warning. SQL Injection Attack Detected via '
        'libinjection [file "@owasp_crs/REQUEST-942-APPLICATION-ATTACK-SQLI.conf"] '
        '[line "5886"] [id "942100"] [rev ""] [msg "SQL Injection Attack Detected via '
        "libinjection\"] [data \"Matched Data: s&sos found within ARGS:q: 1' OR '1'='1\"] "
        '[severity "critical"] [hostname ""] [uri "' + SQLI_URI + '"] [unique_id "wFQfvaDu"]',
    }
)
WAF_SCORE = json.dumps(
    {
        "level": "error",
        "ts": TS,
        "logger": "http.handlers.waf",
        "msg": '[client "198.51.100.140"] Coraza: Warning. Inbound Anomaly Score Exceeded '
        '(Total Score: 5) [id "949110"] [msg "Inbound Anomaly Score Exceeded (Total Score: 5)"] '
        '[uri "' + SQLI_URI + '"] [unique_id "wFQfvaDu"]',
    }
)
WAF_VIOLATION = json.dumps(
    {
        "level": "error",
        "ts": TS,
        "logger": "http.handlers.waf",
        "msg": "WAF rule violation detected",
        "hostname": "git.example.org",
        "uri": SQLI_URI,
        "client_ip": "198.51.100.140",
        "unique_id": "wFQfvaDu",
    }
)


def access(uri="/", status=200, ip="192.0.2.10", reason=None, host="git.example.org", **kw):
    entry = {
        "level": "info",
        "ts": TS + 0.002,
        "logger": "http.log.access.tesseract_access",
        "msg": "handled request",
        "request": {
            "remote_ip": ip,
            "client_ip": ip,
            "proto": "HTTP/2.0",
            "method": "GET",
            "host": host,
            "uri": uri,
            "headers": {"User-Agent": ["curl/8"]},
            **kw,
        },
        "duration": 0.0123,
        "size": 512,
        "status": status,
    }
    if reason:
        entry["tesseract_reason"] = reason
    return json.dumps(entry)


def test_parse_access() -> None:
    p = parse_access(access(reason="ip", status=403))
    assert p["host"] == "git.example.org" and p["reason"] == "ip" and p["status"] == 403
    assert p["duration_ms"] == 12.3 and p["user_agent"] == "curl/8"
    assert parse_access('{"msg": "other"}') is None
    assert parse_access("kein json") is None


def test_waf_correlation() -> None:
    tracker = WafTracker()
    violations = tracker.feed([WAF_WARNING, WAF_SCORE, WAF_VIOLATION])
    assert violations == [("198.51.100.140", "git.example.org")]
    ev = tracker.take("198.51.100.140", SQLI_URI, TS)
    assert ev.rules == [942100] and ev.score == 5 and ev.blocked
    assert ev.msgs == ["SQL Injection Attack Detected via libinjection"]
    assert tracker.take("198.51.100.140", SQLI_URI, TS) is None


def test_access_log_config_and_reasons() -> None:
    from tesseract.caddy.config import HostSpec

    host = HostSpec(
        id=1,
        domain="git.example.org",
        upstream_scheme="http",
        upstream_host="10.0.0.1",
        upstream_port=80,
        websockets=True,
        force_https=True,
        compression=False,
        ip_mode="block",
        ip_ranges=("203.0.113.0/24",),
    )
    spec = dict(
        admin_listen="x",
        hosts=[host],
        banned=("198.51.100.1",),
        controller_domain="t.example.org",
        controller_upstream="t:8000",
    )
    plain = json.dumps(build_config(NodeSpec(**spec)))
    assert "log_append" not in plain and "_tesseract_reason" not in plain
    cfg = build_config(NodeSpec(**spec, access_log_file="/var/log/tesseract/access.log"))
    raw = json.dumps(cfg)
    assert "_tesseract_reason" not in raw
    https = cfg["apps"]["http"]["servers"]["https"]
    assert https["logs"] == {
        "default_logger_name": "tesseract_access",
        "skip_hosts": ["t.example.org"],
    }
    assert cfg["logging"]["logs"]["tesseract_access"]["writer"]["filename"].endswith("access.log")
    for reason in ("ip", "ban"):
        assert (
            json.dumps({"handler": "log_append", "key": "tesseract_reason", "value": reason}) in raw
        )
    # auch die Sperr-Route im HTTP-Server bekommt ihren Grund
    http_ban = next(
        r for r in cfg["apps"]["http"]["servers"]["http"]["routes"] if r.get("@id") == "banned-http"
    )
    assert http_ban["handle"][0]["handler"] == "log_append"


def _local_ingest(client: TestClient, access_lines, waf_lines=()) -> None:
    collector: Collector = client.app.state.logs
    with client.app.state.db.sessionmaker() as db:
        collector.local(db, list(access_lines), list(waf_lines))
        db.commit()


def test_ingest_search_and_detail(auth_client: TestClient) -> None:
    _local_ingest(
        auth_client,
        [
            access(),
            access("/admin", status=403, reason="mtls", host="fotos.example.org"),
            access(SQLI_URI, status=403, ip="198.51.100.140"),
            access("/wp-login.php", status=403, ip="192.0.2.77", reason="ip"),
            access("/api", status=502),
        ],
        [WAF_WARNING, WAF_SCORE, WAF_VIOLATION],
    )
    page = auth_client.get("/api/logs").json()
    assert len(page["entries"]) == 5
    assert page["sources"][0]["node"] == "local" and page["sources"][0]["last_entry_at"]
    waf = next(e for e in page["entries"] if e["reason"] == "waf")
    assert waf["waf_rules"] == [942100] and waf["waf_score"] == 5 and waf["node"] == "local"

    def ids(**params) -> list[str]:
        r = auth_client.get("/api/logs", params=params)
        assert r.status_code == 200, r.text
        return [e["uri"] for e in r.json()["entries"]]

    assert ids(filter="waf") == [SQLI_URI]
    assert ids(filter="mtls") == ["/admin"]
    assert ids(filter="ip") == ["/wp-login.php"]
    assert len(ids(filter="denied")) == 4
    assert ids(q="status:5xx") == ["/api"]
    assert ids(q="host:fotos") == ["/admin"]
    assert ids(q="rule:942100") == [SQLI_URI]
    assert ids(q="rule:94210") == []
    assert ids(q="ip:192.0.2.77") == ["/wp-login.php"]
    assert ids(q="wp-login") == ["/wp-login.php"]
    assert ids(q="node:local status:403 reason:ip") == ["/wp-login.php"]
    assert auth_client.get("/api/logs", params={"q": "status:abc"}).status_code == 422
    # Live: nur Neues
    newest = page["entries"][0]["id"]
    assert ids(after_id=newest) == []

    detail = auth_client.get(f"/api/logs/{waf['id']}").json()
    assert detail["ip_requests"] == 1 and detail["ip_denied"] == 1
    assert detail["host_id"] is None and detail["ip_banned"] is False


def test_exclude_rule_from_log(auth_client: TestClient, caddy: FakeCaddy) -> None:
    host = auth_client.post(
        "/api/hosts", json={**HOST, "domain": "git.example.org", "waf_mode": "block"}
    ).json()["host"]
    _local_ingest(
        auth_client,
        [access(SQLI_URI, status=403, ip="198.51.100.140")],
        [WAF_WARNING, WAF_SCORE, WAF_VIOLATION],
    )
    entry = auth_client.get("/api/logs", params={"filter": "waf"}).json()["entries"][0]
    r = auth_client.post(f"/api/logs/{entry['id']}/exclude")
    assert r.status_code == 200 and r.json()["added"] == [942100], r.text
    h = auth_client.get(f"/api/hosts/{host['id']}").json()
    assert h["waf_exclusions"] == [942100]
    assert "SecRuleRemoveById 942100" in json.dumps(caddy.last)
    # zweimal: nichts Neues
    assert auth_client.post(f"/api/logs/{entry['id']}/exclude").json()["added"] == []
    versions = auth_client.get(f"/api/hosts/{host['id']}/versions").json()
    assert versions[0]["comment"].startswith("Ausnahme aus Log")


def test_agent_logs(auth_client: TestClient) -> None:
    agent, created = _joined(auth_client)
    r = agent.post(
        "/api/agent/logs",
        {
            "access": [access(SQLI_URI, status=403, ip="198.51.100.140")],
            "waf": [WAF_WARNING, WAF_VIOLATION],
        },
    )
    assert r.status_code == 200 and r.json()["entries"] == 1, r.text
    e = auth_client.get("/api/logs").json()["entries"][0]
    assert e["node"] == "pi-eltern" and e["reason"] == "waf"


def test_prune(auth_client: TestClient) -> None:
    from datetime import timedelta

    from tesseract.db.models import utcnow

    _local_ingest(auth_client, [access()])
    with auth_client.app.state.db.sessionmaker() as db:
        node = db.scalar(select(Node))
        db.add(
            LogEntry(ts=utcnow() - timedelta(days=40), node_id=node.id, host="x", ip="192.0.2.1")
        )
        db.commit()
        assert auth_client.app.state.logs.prune(db) == 1
        db.commit()
    assert len(auth_client.get("/api/logs").json()["entries"]) == 1
