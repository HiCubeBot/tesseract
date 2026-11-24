"""Phase 5: Benachrichtigungen – Ereignisse aus dem Audit-Log, Bündeln, Ruhezeit, Kanäle."""

import hashlib
import hmac
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi.testclient import TestClient

from tesseract import audit
from tesseract import notify as n


class Hook:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.fail = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            return httpx.Response(500)
        self.requests.append(request)
        return httpx.Response(200)


def _setup(c: TestClient, hook: Hook, **cfg) -> None:
    c.app.state.notifier.sender.transport = httpx.MockTransport(hook.handler)
    body = {
        "ntfy": {"enabled": True, "url": "https://ntfy.example.org/tesseract", "token": "tk_1"},
        "webhook": {"enabled": True, "url": "https://hooks.example.org/x", "secret": "geheim"},
        "rules": {
            "ip_banned": {"level": "warn", "channels": ["ntfy", "webhook"]},
            "node_offline": {"level": "critical", "channels": ["ntfy"]},
        },
        "quiet": {"enabled": False, "start": 22, "end": 7, "timezone": "Europe/Berlin"},
        "bundle_minutes": 15,
        **cfg,
    }
    r = c.put("/api/settings/notify", json=body)
    assert r.status_code == 200, r.text


def _run(c: TestClient) -> int:
    with c.app.state.db.sessionmaker() as db:
        cfg = n.get_config(db)
        c.app.state.notifier.collect(db, cfg)
        return c.app.state.notifier.flush(n.get_config(db))


def _ban(c: TestClient, ip: str) -> None:
    with c.app.state.db.sessionmaker() as db:
        audit.record(
            db,
            actor="system",
            action="ip_banned",
            target=ip,
            details={"hits": 20, "host": "git.example.org", "hours": 24},
        )
        db.commit()


def test_settings_hide_secrets(auth_client: TestClient) -> None:
    _setup(auth_client, Hook())
    out = auth_client.get("/api/settings/notify").json()
    assert out["ntfy"] == {
        "enabled": True,
        "url": "https://ntfy.example.org/tesseract",
        "token_set": True,
    }
    assert out["webhook"]["secret_set"] is True and "secret_enc" not in json.dumps(out)
    assert {e["id"] for e in out["events"]} >= {"node_offline", "ip_banned"}
    bad = auth_client.put("/api/settings/notify", json={"ntfy": {"enabled": True, "url": "x"}})
    assert bad.status_code == 422
    bad = auth_client.put("/api/settings/notify", json={"rules": {"gibts": {"level": "info"}}})
    assert bad.status_code == 422


def test_events_bundling_and_channels(auth_client: TestClient) -> None:
    hook = Hook()
    _setup(auth_client, hook)
    assert _run(auth_client) == 0  # erster Lauf setzt nur den Startpunkt
    _ban(auth_client, "198.51.100.1")
    assert _run(auth_client) == 2  # ntfy + Webhook
    ntfy, webhook = hook.requests
    assert ntfy.url == "https://ntfy.example.org/tesseract"
    assert ntfy.headers["Authorization"] == "Bearer tk_1" and ntfy.headers["Priority"] == "4"
    assert ntfy.headers["Content-Type"] == "text/plain; charset=utf-8"
    assert "198.51.100.1 gesperrt (20 WAF-Treffer auf git.example.org)" in ntfy.content.decode()
    body = json.loads(webhook.content)
    assert body["event"] == "ip_banned" and body["level"] == "warn"
    sig = hmac.new(b"geheim", webhook.content, hashlib.sha256).hexdigest()
    assert webhook.headers["X-Tesseract-Signature"] == f"sha256={sig}"

    # innerhalb des Bündelfensters: sammeln statt senden
    _ban(auth_client, "198.51.100.2")
    _ban(auth_client, "198.51.100.3")
    assert _run(auth_client) == 0
    notifier = auth_client.app.state.notifier
    notifier.last_sent = {k: 0.0 for k in notifier.last_sent}  # Fenster vorbei
    assert _run(auth_client) == 2
    text = hook.requests[-2].content.decode()
    assert "198.51.100.2" in text and "198.51.100.3" in text

    # von Hand gesperrt → keine Meldung
    with auth_client.app.state.db.sessionmaker() as db:
        audit.record(db, actor="admin", action="ip_banned", target="203.0.113.1")
        db.commit()
    notifier.last_sent.clear()
    assert _run(auth_client) == 0


def test_quiet_hours_hold_non_critical(auth_client: TestClient) -> None:
    hook = Hook()
    _setup(auth_client, hook)
    cfg = {"quiet": {"enabled": True, "start": 22, "end": 7, "timezone": "Europe/Berlin"}}
    tz = ZoneInfo("Europe/Berlin")
    assert n.in_quiet(cfg, datetime(2026, 11, 18, 23, tzinfo=tz))
    assert n.in_quiet(cfg, datetime(2026, 11, 18, 6, tzinfo=tz))
    assert not n.in_quiet(cfg, datetime(2026, 11, 18, 12, tzinfo=tz))

    # In der Ruhezeit: Warnung wartet, Kritisches geht sofort
    with auth_client.app.state.db.sessionmaker() as db:
        n.set_config(db, {"cursor": 0})
        db.commit()
    _run(auth_client)
    import tesseract.notify as mod

    orig = mod.in_quiet
    mod.in_quiet = lambda cfg, now=None: True
    try:
        _ban(auth_client, "198.51.100.9")
        with auth_client.app.state.db.sessionmaker() as db:
            audit.record(db, actor="system", action="node_offline", target="pi", details={})
            db.commit()
        assert _run(auth_client) == 1
        assert hook.requests[-1].headers["Priority"] == "5"
        assert len(auth_client.app.state.notifier.pending) == 2  # Warnung wartet (2 Kanäle)
    finally:
        mod.in_quiet = orig
    # Ruhezeit vorbei (hier: ausgeschaltet) → die Warnung geht raus
    auth_client.put(
        "/api/settings/notify",
        json={"quiet": {"enabled": False, "start": 22, "end": 7, "timezone": "UTC"}},
    )
    assert _run(auth_client) == 2


def test_test_message_and_errors(auth_client: TestClient) -> None:
    hook = Hook()
    _setup(auth_client, hook)
    r = auth_client.post("/api/settings/notify/test", json={"channel": "ntfy"})
    assert r.json() == {"ok": True, "error": None}
    assert (
        auth_client.post("/api/settings/notify/test", json={"channel": "email"}).status_code == 409
    )
    hook.fail = True
    r = auth_client.post("/api/settings/notify/test", json={"channel": "webhook"})
    assert r.json()["ok"] is False and "500" in r.json()["error"]


def test_email(auth_client: TestClient) -> None:
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None, context=None):
            self.calls = [("connect", host, port)]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            sent.append(self.calls)

        def starttls(self, context=None):
            self.calls.append(("starttls",))

        def login(self, user, password):
            self.calls.append(("login", user, password))

        def send_message(self, m):
            self.calls.append(("send", m["To"], m["Subject"], m.get_content()))

    auth_client.app.state.notifier.sender.smtp_factory = FakeSMTP
    r = auth_client.put(
        "/api/settings/notify",
        json={
            "email": {
                "enabled": True,
                "host": "smtp.example.org",
                "user": "tesseract@example.org",
                "password": "pw",
                "to": ["ich@example.org"],
            }
        },
    )
    assert r.json()["email"]["password_set"] is True
    assert auth_client.post("/api/settings/notify/test", json={"channel": "email"}).json()["ok"]
    calls = sent[0]
    assert calls[1] == ("starttls",) and calls[2] == ("login", "tesseract@example.org", "pw")
    assert calls[3][1] == "ich@example.org" and "Testmeldung" in calls[3][2]


def test_node_offline_transition(auth_client: TestClient) -> None:
    from datetime import timedelta

    from sqlalchemy import select

    from tesseract.db.models import AuditEntry, Node, utcnow
    from tesseract.nodes import track_online

    seen: dict[int, bool] = {}
    with auth_client.app.state.db.sessionmaker() as db:
        node = db.get(Node, 1)
        node.last_seen_at = utcnow()
        track_online(db, seen)  # Ausgangszustand
        node.last_seen_at = utcnow() - timedelta(minutes=5)
        node.kind = "agent"
        node.cert_fingerprint = "ab" * 32
        track_online(db, seen)
        db.commit()
        actions = list(db.scalars(select(AuditEntry.action).where(AuditEntry.target == "local")))
    assert actions == ["node_offline"]


def test_ntfy_errors_and_basic_auth() -> None:
    import httpx

    from tesseract.notify import Message, NotifyError, Sender
    from tesseract.secretbox import SecretBox

    box = SecretBox(b"0" * 32)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "proxy" in str(request.url):
            return httpx.Response(403, text="Kein Zugang")
        if request.headers.get("Authorization", "").startswith("Basic"):
            return httpx.Response(200, json={"id": "x"})
        return httpx.Response(403, json={"code": 40301, "http": 403, "error": "forbidden"})

    s = Sender(box, httpx.MockTransport(handler))
    msg = Message("test", "info", "Test", ["Hallo"])
    url = "https://ntfy.example.org/tesseract"
    try:
        s._ntfy({"url": url, "token_enc": ""}, msg)
    except NotifyError as e:
        assert "kein anonymes Senden" in str(e) and "ntfy access <benutzer> tesseract rw" in str(e)
    else:
        raise AssertionError("403 erwartet")
    from tesseract.notify import SECRET_CONTEXT

    enc = box.encrypt(b"anna:geheim", SECRET_CONTEXT)
    s._ntfy({"url": url, "token_enc": enc}, msg)
    assert seen[-1].headers["Authorization"].startswith("Basic ")
    tok = box.encrypt(b"tk_abc", SECRET_CONTEXT)
    try:
        s._ntfy({"url": url, "token_enc": tok}, msg)
    except NotifyError as e:
        assert "darf nicht auf „tesseract“ senden" in str(e)
    try:
        s._ntfy({"url": "https://proxy.example.org/t", "token_enc": tok}, msg)
    except NotifyError as e:
        assert "nicht von ntfy" in str(e)
