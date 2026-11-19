import json
from pathlib import Path

from fastapi.testclient import TestClient

from tesseract.autoban import AutoBan, LogTail, expire_bans, parse_violation
from tesseract.caddy.config import NodeSpec, build_config
from tesseract.db.models import Ban, utcnow
from tests.conftest import FakeCaddy


def _line(ip: str, host: str = "git.example.org", msg: str = "WAF rule violation detected") -> str:
    return json.dumps({"level": "error", "msg": msg, "client_ip": ip, "hostname": host})


def test_parse() -> None:
    assert parse_violation(_line("198.51.100.7")) == ("198.51.100.7", "git.example.org")
    assert parse_violation(_line("198.51.100.7", msg="other")) is None
    assert parse_violation(_line("keine-ip")) is None
    assert parse_violation("kein json") is None


def test_tail_rotation(tmp_path: Path) -> None:
    f = tmp_path / "waf.log"
    f.write_text("alt\n")
    tail = LogTail(f)
    assert tail.read_new() == []  # Start: ans Ende springen
    with f.open("a") as h:
        h.write("eins\nzwei\nhalb")
    assert tail.read_new() == ["eins", "zwei"]
    with f.open("a") as h:
        h.write("e\n")
    assert tail.read_new() == ["halbe"]
    f.write_text("neu\n")  # rotiert (kleiner)
    assert tail.read_new() == ["neu"]


def test_ban_config() -> None:
    cfg = build_config(
        NodeSpec(
            admin_listen="x",
            controller_domain="t.example.org",
            controller_upstream="tesseract:8000",
            banned=("198.51.100.7",),
            waf_log_file="/var/log/tesseract/waf.log",
        )
    )
    routes = cfg["apps"]["http"]["servers"]["https"]["routes"]
    # Oberfläche zuerst (bleibt erreichbar), dann die Sperre
    assert [r.get("@id") for r in routes] == ["controller", "banned"]
    assert routes[1]["match"] == [{"client_ip": {"ranges": ["198.51.100.7"]}}]
    log = cfg["logging"]["logs"]["tesseract_waf"]
    assert log["include"] == ["http.handlers.waf"] and log["writer"]["filename"].endswith("waf.log")


def test_autoban_flow(auth_client: TestClient, caddy: FakeCaddy) -> None:
    auth_client.put(
        "/api/settings/general",
        json={"autoban_hits": 3, "autoban_window_minutes": 10, "autoban_exempt": ["10.0.0.0/8"]},
    )
    db = auth_client.app.state.db.sessionmaker()
    clock = [1000.0]
    banner = AutoBan(clock=lambda: clock[0])
    bad, own = "198.51.100.7", "10.1.2.3"
    assert banner.feed(db, [(bad, "git.example.org")] * 2) == []
    created = banner.feed(db, [(bad, "git.example.org"), (own, "x")] * 3)
    db.commit()
    assert [b.ip for b in created] == [bad]  # eigenes Netz ausgenommen
    # Zeitfenster: alte Treffer zählen nicht mehr
    clock[0] += 11 * 60
    assert banner.feed(db, [("203.0.113.9", "x")] * 2) == []

    bans = auth_client.get("/api/bans").json()
    assert bans[0]["ip"] == bad and bans[0]["hits"] == 3 and bans[0]["active"]

    # Ablauf
    b = db.get(Ban, bans[0]["id"])
    b.expires_at = utcnow()
    assert [x.ip for x in expire_bans(db)] == [bad]
    db.commit()
    db.close()
    assert auth_client.get("/api/bans").json() == []


def test_manual_ban(auth_client: TestClient, caddy: FakeCaddy) -> None:
    r = auth_client.post("/api/bans", json={"ip": "203.0.113.0/24", "hours": 2})
    assert r.status_code == 201
    ban = r.json()
    routes = caddy.last["apps"]["http"]["servers"]["https"]["routes"]
    assert any(r.get("@id") == "banned" for r in routes)
    assert auth_client.post("/api/bans", json={"ip": "203.0.113.0/24"}).status_code == 409
    assert auth_client.post("/api/bans", json={"ip": "quatsch"}).status_code == 422

    assert auth_client.delete(f"/api/bans/{ban['id']}").json()["active"] is False
    routes = caddy.last["apps"]["http"]["servers"]["https"]["routes"]
    assert not any(r.get("@id") == "banned" for r in routes)
    actions = [e["action"] for e in auth_client.get("/api/audit").json()]
    assert actions[:2] == ["ip_unbanned", "ip_banned"]


def test_permanent_ban(auth_client: TestClient, caddy: FakeCaddy) -> None:
    r = auth_client.post("/api/bans", json={"ip": "192.0.2.66", "hours": None, "reason": "Scanner"})
    assert r.status_code == 201
    ban = r.json()
    assert ban["expires_at"] is None and ban["active"]
    routes = caddy.last["apps"]["http"]["servers"]["https"]["routes"]
    assert any(r.get("@id") == "banned" for r in routes)

    # läuft nie ab
    db = auth_client.app.state.db.sessionmaker()
    assert expire_bans(db) == []
    db.close()
    assert [b["ip"] for b in auth_client.get("/api/bans").json()] == ["192.0.2.66/32"]
    assert auth_client.post("/api/bans", json={"ip": "192.0.2.66"}).status_code == 409
    audit = auth_client.get("/api/audit").json()[0]
    assert audit["action"] == "ip_banned" and audit["details"]["hours"] == "dauerhaft"

    # bleibt von Hand aufhebbar
    assert auth_client.delete(f"/api/bans/{ban['id']}").json()["active"] is False
    assert auth_client.get("/api/bans").json() == []
