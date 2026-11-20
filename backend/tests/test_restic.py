"""Restic als Sicherungsziel – mit einem nachgebauten restic-Prozess."""

import json
import subprocess

import pytest
from fastapi.testclient import TestClient

from tesseract import backup as b

PASS = "eine-lange-passphrase"


class FakeRestic:
    """Merkt sich Snapshots im Speicher und beantwortet die Befehle wie restic."""

    def __init__(self) -> None:
        self.exists = False
        self.snaps: list[dict] = []
        self.data: dict[str, bytes] = {}
        self.calls: list[list[str]] = []
        self.env: dict[str, str] = {}

    def __call__(self, cmd, input=None, capture_output=True, env=None, timeout=None):
        args = cmd[1:]
        self.calls.append(args)
        self.env = env

        def done(code=0, out=b"", err=b""):
            return subprocess.CompletedProcess(cmd, code, out, err)

        if env.get("RESTIC_PASSWORD") != "repo-passwort":
            return done(1, err=b"Fatal: wrong password or no key found")
        if args[0] == "init":
            self.exists = True
            return done(out=b"created restic repository")
        if not self.exists:
            return done(10, err=b"Fatal: repository does not exist: unable to open config file")
        if args[:2] == ["cat", "config"]:
            return done(out=b"{}")
        if args[0] == "backup":
            name = args[args.index("--stdin-filename") + 1]
            sid = f"{len(self.snaps) + 1:064x}"
            self.snaps.append(
                {"id": sid, "paths": [f"/{name}"], "summary": {"total_bytes_processed": len(input)}}
            )
            self.data[sid] = input
            return done()
        if args[0] == "snapshots":
            return done(out=json.dumps(self.snaps).encode())
        if args[0] == "dump":
            return done(out=self.data[args[1]])
        if args[0] == "forget":
            if "--keep-last" in args:
                keep = int(args[args.index("--keep-last") + 1])
                self.snaps = self.snaps[-keep:]
            else:
                self.snaps = [s for s in self.snaps if s["id"] != args[-1]]
            return done()
        return done(1, err=b"unknown command")


def test_target_roundtrip() -> None:
    fake = FakeRestic()
    t = b.ResticTarget("sftp:nas:/backup", "repo-passwort", {"AWS_REGION": "eu"}, runner=fake)
    assert t.list() == []  # Repository fehlt noch – keine Sicherungen
    assert t.ensure_repo() is True and t.ensure_repo() is False
    for i in range(3):
        t.put(f"tesseract-2026111{i}-030000.tsbak", f"daten{i}".encode())
    assert [n for n, _ in t.list()] == [f"tesseract-2026111{i}-030000.tsbak" for i in range(3)]
    assert t.get("tesseract-20261111-030000.tsbak") == b"daten1"
    assert fake.env["RESTIC_REPOSITORY"] == "sftp:nas:/backup" and fake.env["AWS_REGION"] == "eu"
    # Aufräumen über restic forget --keep-last
    assert b.prune(t, 2) == ["tesseract-20261110-030000.tsbak"]
    forget = next(c for c in fake.calls if "--keep-last" in c)
    assert forget[forget.index("--group-by") + 1] == "host,tags"
    with pytest.raises(b.BackupError, match="Ungültiger Name"):
        t.get("../etc/passwd")
    bad = b.ResticTarget("x", "falsch", runner=fake)
    with pytest.raises(b.BackupError, match="wrong password"):
        bad.ensure_repo()


def test_parse_env() -> None:
    assert b.parse_env("# Kommentar\nAWS_ACCESS_KEY_ID=abc\n\nB2_ACCOUNT_KEY = x=y\n") == {
        "AWS_ACCESS_KEY_ID": "abc",
        "B2_ACCOUNT_KEY": "x=y",
    }
    with pytest.raises(b.BackupError):
        b.parse_env("kein-gleich")
    with pytest.raises(b.BackupError, match="RESTIC_PASSWORD"):
        b.parse_env("RESTIC_PASSWORD=x")


def test_api(auth_client: TestClient, monkeypatch) -> None:
    fake = FakeRestic()
    real = b.restic_target
    monkeypatch.setattr(b, "restic_target", lambda rc, s, box, runner=None: real(rc, s, box, fake))

    r = auth_client.put("/api/backups/config", json={"restic": {"enabled": True, "repository": ""}})
    assert r.status_code == 422
    r = auth_client.put(
        "/api/backups/config",
        json={
            "passphrase": PASS,
            "local": False,
            "restic": {
                "enabled": True,
                "repository": "rest:http://nas:8000/",
                "password": "repo-passwort",
                "env": "AWS_ACCESS_KEY_ID=abc",
            },
        },
    )
    assert r.status_code == 200, r.text
    rc = r.json()["restic"]
    assert rc == {
        "enabled": True,
        "repository": "rest:http://nas:8000/",
        "password_set": True,
        "env_set": True,
    }
    assert "repo-passwort" not in r.text and "abc" not in r.text

    check = auth_client.post("/api/backups/restic/check").json()
    assert check["ok"] and check["created"] and check["snapshots"] == 0

    run = auth_client.post("/api/backups").json()
    assert run["ok"] and run["targets"] == ["restic"]
    listed = auth_client.get("/api/backups").json()
    assert listed[0]["target"] == "restic" and listed[0]["name"] == run["name"]

    test = auth_client.post("/api/backups/test", json={"target": "restic", "name": run["name"]})
    assert test.json()["ok"] is True
    dl = auth_client.get(f"/api/backups/restic/{run['name']}")
    assert dl.status_code == 200 and dl.content.startswith(b.MAGIC)

    # Passwort bleibt erhalten, wenn es nicht mitgeschickt wird
    r = auth_client.put(
        "/api/backups/config",
        json={"restic": {"enabled": True, "repository": "rest:http://nas:8000/"}},
    )
    assert r.json()["restic"]["password_set"] is True
