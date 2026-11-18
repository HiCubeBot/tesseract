"""Phase 6: Verschlüsselte Sicherungen, Ziele, Zeitplan, Wiederherstellen."""

import re
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from tesseract import backup as b
from tests.conftest import FakeCaddy
from tests.test_hosts import HOST

PHRASE = "backup-passphrase-123"


class FakeS3:
    """Speichert Objekte im Speicher und prüft, dass signiert wurde."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("AWS4-HMAC-SHA256 Credential=AK/")
        path = request.url.path  # /bucket/key
        _, bucket, *rest = path.split("/", 2)
        key = rest[0] if rest else ""
        if request.method == "PUT":
            self.objects[key] = request.content
            return httpx.Response(200)
        if request.method == "DELETE":
            self.objects.pop(key, None)
            return httpx.Response(204)
        if request.method == "GET" and key:
            return httpx.Response(200, content=self.objects[key])
        prefix = request.url.params.get("prefix", "")
        items = "".join(
            f"<Contents><Key>{k}</Key><Size>{len(v)}</Size></Contents>"
            for k, v in sorted(self.objects.items())
            if k.startswith(prefix)
        )
        return httpx.Response(200, text=f"<ListBucketResult>{items}</ListBucketResult>")


def _configure(c: TestClient, **kw) -> dict:
    r = c.put("/api/backups/config", json={"passphrase": PHRASE, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_encrypt_roundtrip_and_tamper() -> None:
    data = b.encrypt(b"geheim", PHRASE, {"app": "tesseract"})
    assert b"geheim" not in data
    assert b.decrypt(data, PHRASE)[1] == b"geheim"
    with pytest.raises(b.BackupError, match="Passphrase falsch"):
        b.decrypt(data, "falsche-passphrase-1")
    # Kopf ist mit authentifiziert
    tampered = data.replace(b'"app":"tesseract"', b'"app":"tesserakt"')
    with pytest.raises(b.BackupError):
        b.decrypt(tampered, PHRASE)
    with pytest.raises(b.BackupError, match="Format"):
        b.decrypt(b"irgendwas", PHRASE)


def test_backup_and_restore(auth_client: TestClient, caddy: FakeCaddy) -> None:
    assert auth_client.post("/api/backups").status_code == 409  # ohne Passphrase
    assert auth_client.put("/api/backups/config", json={"passphrase": "kurz"}).status_code == 422
    cfg = _configure(auth_client, keep=2)
    assert cfg["passphrase_set"] is True and cfg["local"]["enabled"] is True

    auth_client.post("/api/hosts", json={**HOST, "domain": "vorher.example.org"})
    r = auth_client.post("/api/backups")
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    first = r.json()["name"]
    listing = auth_client.get("/api/backups").json()
    assert listing == [{"target": "local", "name": first, "size": r.json()["size"]}]

    # Datei herunterladen: verschlüsselt, ohne Klartext
    raw = auth_client.get(f"/api/backups/local/{first}").content
    assert raw.startswith(b"TSBAK1\n") and b"vorher.example.org" not in raw

    # Test ohne Änderung
    t = auth_client.post("/api/backups/test", json={"target": "local", "name": first}).json()
    assert t["ok"] is True and t["manifest"]["counts"]["hosts"] == 1
    bad = auth_client.post(
        "/api/backups/test",
        json={"target": "local", "name": first, "passphrase": "falsche-passphrase-1"},
    ).json()
    assert bad["ok"] is False and "Passphrase" in bad["error"]

    # Danach ändern, dann zurückholen
    host_id = auth_client.get("/api/hosts").json()[0]["id"]
    auth_client.delete(f"/api/hosts/{host_id}")
    auth_client.post("/api/hosts", json={**HOST, "domain": "nachher.example.org"})
    loads = len(caddy.loaded)
    r = auth_client.post("/api/backups/restore", json={"target": "local", "name": first})
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    # Session gehört zum alten Stand? Admin bleibt gleich – neu anmelden reicht
    from tests.conftest import ADMIN_PASSWORD

    auth_client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    domains = [h["domain"] for h in auth_client.get("/api/hosts").json()]
    assert domains == ["vorher.example.org"]
    # Nodes bekommen den wiederhergestellten Stand
    assert len(caddy.loaded) > loads and "vorher.example.org" in str(caddy.last)
    actions = [e["action"] for e in auth_client.get("/api/audit").json()]
    assert "backup_restored" in actions
    assert auth_client.get("/api/audit/verify").json()["ok"] is True


def test_keep_and_upload_restore(auth_client: TestClient) -> None:
    _configure(auth_client, keep=2)
    target = b.LocalTarget(b.local_dir(auth_client.app.state.settings))
    for old in ("tesseract-20200101-000000.tsbak", "tesseract-20210101-000000.tsbak"):
        target.put(old, b"alt")
    r = auth_client.post("/api/backups").json()
    # die beiden neuesten bleiben: die vom Jahr 2021 und die gerade erstellte
    assert [n for n, _ in target.list()] == ["tesseract-20210101-000000.tsbak", r["name"]]

    data = target.get(r["name"])
    r = auth_client.post(
        "/api/backups/restore/upload",
        content=data,
        headers={"X-Backup-Passphrase": PHRASE, "Content-Type": "application/octet-stream"},
    )
    assert r.status_code == 200, r.text
    r = auth_client.post(
        "/api/backups/restore/upload", content=data, headers={"X-Backup-Passphrase": "x" * 12}
    )
    assert r.status_code in (401, 422)


def test_s3_target(auth_client: TestClient) -> None:
    s3 = FakeS3()
    auth_client.app.state.backup_transport = httpx.MockTransport(s3.handler)
    cfg = _configure(
        auth_client,
        local=False,
        s3={
            "enabled": True,
            "endpoint": "https://minio.example.org",
            "bucket": "sicherungen",
            "access_key": "AK",
            "secret_key": "SK",
            "prefix": "tesseract",
        },
    )
    assert cfg["s3"]["secret_key_set"] is True and "secret_key_enc" not in str(cfg)
    r = auth_client.post("/api/backups").json()
    assert r["ok"] is True and r["targets"] == ["s3"]
    assert list(s3.objects) == [f"tesseract/{r['name']}"]
    listing = auth_client.get("/api/backups").json()
    assert listing[0]["target"] == "s3"
    t = auth_client.post("/api/backups/test", json={"target": "s3", "name": r["name"]}).json()
    assert t["ok"] is True


def test_failed_backup_is_audited(auth_client: TestClient) -> None:
    _configure(auth_client, local=False)
    r = auth_client.post("/api/backups")
    assert r.status_code == 409 and "Kein Ziel" in r.json()["detail"]
    actions = [e["action"] for e in auth_client.get("/api/audit").json()]
    assert "backup_failed" in actions
    from tesseract.notify import ACTION_EVENT

    assert ACTION_EVENT["backup_failed"] == "backup_failed"


def test_schedule() -> None:
    cfg = {"schedule": "daily", "hour": 3, "timezone": "UTC"}
    since = datetime(2026, 11, 18, 12, tzinfo=UTC)
    now = datetime(2026, 11, 19, 3, 0, 30, tzinfo=UTC)
    assert not b.is_due(cfg, None, since, datetime(2026, 11, 18, 20, tzinfo=UTC))
    assert b.is_due(cfg, None, since, now)
    assert not b.is_due(cfg, now, since, now + timedelta(hours=5))
    assert b.next_run(cfg, now) == datetime(2026, 11, 20, 3, tzinfo=UTC)
    weekly = {"schedule": "weekly", "hour": 2, "weekday": 6, "timezone": "UTC"}
    # 22.11.2026 ist ein Sonntag
    assert b.next_run(weekly, datetime(2026, 11, 19, tzinfo=UTC)) == datetime(
        2026, 11, 22, 2, tzinfo=UTC
    )
    hourly = {"schedule": "hourly", "timezone": "UTC"}
    assert b.is_due(hourly, None, since, since + timedelta(minutes=61))
    assert not b.is_due({"schedule": "off"}, None, since, now)


def test_names_are_validated() -> None:
    with pytest.raises(b.BackupError):
        b._safe("../secret.key")
    assert re.match(b.NAME_RE, "tesseract-20261118-030000.tsbak")


def test_cli_backup_and_restore(settings, monkeypatch, tmp_path, capsys) -> None:
    from tesseract.cli import run

    monkeypatch.setattr("tesseract.cli.get_settings", lambda: settings)
    monkeypatch.setenv("TESSERACT_BACKUP_PASSPHRASE", PHRASE)
    out = tmp_path / "sicherungen"
    out.mkdir()
    run(["backup", "create", "--out", str(out)])
    files = list(out.iterdir())
    assert len(files) == 1 and "Sicherung geschrieben" in capsys.readouterr().out
    run(["backup", "restore", str(files[0])])
    assert "zurückgespielt" in capsys.readouterr().out
    monkeypatch.setenv("TESSERACT_BACKUP_PASSPHRASE", "falsche-passphrase-1")
    with pytest.raises(SystemExit, match="Passphrase falsch"):
        run(["backup", "restore", str(files[0])])
