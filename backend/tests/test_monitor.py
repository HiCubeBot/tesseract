"""Uptime-Monitor, Statistik › Betrieb und öffentliche Statusseite."""

import asyncio
import socket

from fastapi.testclient import TestClient
from sqlalchemy import select

from tesseract import monitor
from tesseract.caddy.config import CONTROLLER_PUBLIC_PATHS
from tesseract.db.models import AuditEntry, Incident, MonitorState, UptimeDaily
from tests.test_hosts import HOST


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_record_confirms_outage(auth_client: TestClient) -> None:
    R = monitor.Result
    fails: dict = {}
    with auth_client.app.state.db.sessionmaker() as db:
        monitor.record(db, [R("host", "a.example.org", True, 5.0)], fails=fails)
        # ein Aussetzer zählt noch nicht
        assert monitor.record(db, [R("host", "a.example.org", False, error="x")], fails=fails) == []
        assert db.get(MonitorState, ("host", "a.example.org")).status == "up"
        ch = monitor.record(db, [R("host", "a.example.org", False, error="refused")], fails=fails)
        assert ch == [("host", "a.example.org", "down")]
        inc = db.scalar(select(Incident))
        assert inc.ended_at is None and inc.error == "refused"
        ch = monitor.record(db, [R("host", "a.example.org", True, 3.0)], fails=fails)
        assert ch == [("host", "a.example.org", "up")] and inc.ended_at is not None
        d = db.scalars(select(UptimeDaily)).one()
        assert d.checks == 4 and d.up == 2 and d.outages == 1 and d.down_seconds == 120
        actions = [a.action for a in db.scalars(select(AuditEntry))]
        assert "host_down" in actions and "host_up" in actions
        db.commit()


def test_check_all_local_node(auth_client: TestClient) -> None:
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()
    up_port = srv.getsockname()[1]
    try:
        auth_client.post(
            "/api/hosts",
            json={
                **HOST,
                "domain": "da.example.org",
                "upstream_host": "127.0.0.1",
                "upstream_port": up_port,
            },
        )
        auth_client.post(
            "/api/hosts",
            json={
                **HOST,
                "domain": "weg.example.org",
                "upstream_host": "127.0.0.1",
                "upstream_port": _free_port(),
            },
        )
        auth_client.post("/api/hosts", json={**HOST, "domain": "aus.example.org", "monitor": False})
        results = asyncio.run(monitor.check_all(auth_client.app))
    finally:
        srv.close()
    by = {(r.kind, r.ref): r for r in results}
    assert by[("node", "local")].ok is True
    assert by[("host", "da.example.org")].ok is True
    assert by[("host", "weg.example.org")].ok is False
    assert ("host", "aus.example.org") not in by


def test_monitor_api_and_status_page(auth_client: TestClient) -> None:
    host = auth_client.post(
        "/api/hosts",
        json={**HOST, "domain": "cloud.example.org", "status_public": True, "status_name": "Cloud"},
    ).json()["host"]
    assert host["status_public"] is True and host["monitor"] is True
    auth_client.post("/api/hosts", json={**HOST, "domain": "geheim.example.org"})
    R = monitor.Result
    with auth_client.app.state.db.sessionmaker() as db:
        monitor.record(db, [R("host", "cloud.example.org", True, 4.0), R("node", "local", True)])
        db.commit()
    m = auth_client.get("/api/monitor").json()
    assert {h["domain"] for h in m["hosts"]} == {"cloud.example.org", "geheim.example.org"}
    cloud = next(h for h in m["hosts"] if h["domain"] == "cloud.example.org")
    assert cloud["status"] == "up" and cloud["pct"] == 100.0 and len(cloud["days"]) == 30
    assert m["nodes"][0]["name"] == "local"
    # standardmäßig aus
    anon = TestClient(auth_client.app)
    assert anon.get("/api/status").status_code == 404
    ops = auth_client.get("/api/stats/operations").json()
    assert ops["status_enabled"] is False
    g = auth_client.put("/api/settings/general", json={"status_page_enabled": True}).json()
    assert g["status_page_enabled"] is True and g["status_page_url"].endswith("/status")
    # andere Einstellungen bleiben unverändert, wenn das Feld fehlt
    g = auth_client.put("/api/settings/general", json={"autoban_hits": 20}).json()
    assert g["status_page_enabled"] is True
    # öffentlich, ohne Anmeldung – nur freigegebene Dienste, ohne Domain
    s = anon.get("/api/status").json()
    assert s["overall"] == "ok"
    assert [x["name"] for x in s["services"]] == ["Cloud"]
    assert "geheim" not in str(s) and len(s["services"][0]["days"]) == 90
    ops = auth_client.get("/api/stats/operations").json()
    assert ops["status_hosts"] == 1 and "records" in ops
    assert anon.get("/api/monitor").status_code == 401


def test_status_paths_only_when_enabled() -> None:
    from tesseract.caddy.config import NodeSpec, public_paths

    off = public_paths(NodeSpec(admin_listen=""))
    on = public_paths(NodeSpec(admin_listen="", controller_status_open=True))
    assert "/status" not in off and "/api/status" not in off
    assert "/status" in on and "/api/status" in on
    assert set(CONTROLLER_PUBLIC_PATHS) == set(on)
