"""Phase 5: Statistik."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from tesseract.db.models import Device, LogEntry, Node, utcnow
from tesseract.stats import family


def _add(client: TestClient, rows: list[dict]) -> None:
    with client.app.state.db.sessionmaker() as db:
        node = db.scalar(select(Node))
        now = utcnow()
        for r in rows:
            db.add(
                LogEntry(
                    ts=now - timedelta(minutes=r.pop("ago", 5)),
                    node_id=node.id,
                    host=r.pop("host", "git.example.org"),
                    ip=r.pop("ip", "192.0.2.10"),
                    **{"status": 200, "duration_ms": 10.0, "size": 100, **r},
                )
            )
        db.commit()


def test_family() -> None:
    assert family(942100) == "SQL-Injection"
    assert family(930130) == "Pfad-Traversal / LFI"
    assert family(1) == "Sonstige"


def test_security_and_traffic(auth_client: TestClient) -> None:
    _add(
        auth_client,
        [
            {"duration_ms": 10.0},
            {"duration_ms": 30.0, "size": 900},
            {"status": 502, "duration_ms": 50.0},
            {
                "status": 403,
                "reason": "waf",
                "waf_rules": [942100],
                "ip": "198.51.100.1",
                "country": "RU",
            },
            {
                "status": 403,
                "reason": "waf",
                "waf_rules": [930130],
                "ip": "198.51.100.1",
                "country": "RU",
            },
            {"status": 403, "reason": "mtls", "host": "fotos.example.org", "ip": "203.0.113.5"},
            {"status": 403, "reason": "ip", "ip": "203.0.113.6"},
            {"status": 200, "ago": 60 * 24 * 3},  # außerhalb von 24 h
        ],
    )
    sec = auth_client.get("/api/stats/security").json()
    assert sec["total"] == 7 and sec["denied"] == 4 and sec["waf_blocked"] == 2
    assert sec["top_ips"][0] == {"ip": "198.51.100.1", "count": 2, "country": "RU", "reason": "waf"}
    assert {a["name"] for a in sec["attacks"]} == {"SQL-Injection", "Pfad-Traversal / LFI"}
    assert sec["countries"] == [{"country": "RU", "count": 2}]
    git = next(h for h in sec["by_host"] if h["host"] == "git.example.org")
    assert git == {"host": "git.example.org", "total": 3, "mtls": 0, "waf": 2, "ip": 1, "other": 0}
    assert sum(sum(v for k, v in h.items() if k != "t") for h in sec["hourly"]) == 4
    assert auth_client.get("/api/stats/security", params={"range": "7d"}).json()["total"] == 8
    assert auth_client.get("/api/stats/security", params={"range": "1y"}).status_code == 422

    tr = auth_client.get("/api/stats/traffic").json()
    assert tr["total"] == 7
    assert tr["composition"] == {"ok": 2, "redirect": 0, "client": 0, "server": 1, "denied": 4}
    git = next(h for h in tr["hosts"] if h["host"] == "git.example.org")
    assert git["requests"] == 6 and git["errors"] == 1 and git["denied"] == 3
    assert git["median_ms"] == 30.0 and git["p95_ms"] == 50.0
    assert git["availability"] == 66.67


def test_usage(auth_client: TestClient) -> None:
    assert (
        auth_client.post("/api/ca/setup", json={"passphrase": "root-passphrase-123"}).status_code
        == 200
    )
    p = auth_client.post("/api/persons", json={"name": "Anna"}).json()
    auth_client.post(f"/api/persons/{p['id']}/devices", json={"name": "iPhone"})
    with auth_client.app.state.db.sessionmaker() as db:
        dev_id = db.scalar(select(Device.id))
    _add(
        auth_client,
        [
            {"device_id": dev_id, "host": "fotos.example.org", "size": 1000},
            {"device_id": dev_id, "host": "fotos.example.org"},
            {"device_id": dev_id, "host": "filme.example.org", "country": "DE"},
            {},  # ohne Gerät zählt nicht
        ],
    )
    u = auth_client.get("/api/stats/usage").json()
    assert u["hosts"] == ["filme.example.org", "fotos.example.org"]
    assert u["matrix"] == [
        {"person": "Anna", "counts": {"fotos.example.org": 2, "filme.example.org": 1}, "total": 3}
    ]
    d = u["devices"][0]
    assert d["name"] == "iPhone" and d["requests"] == 3 and d["top_host"] == "fotos.example.org"
    assert d["countries"] == ["DE"] and d["bytes"] == 1200
    assert sum(h["n"] for h in u["hourly"]) == 3
