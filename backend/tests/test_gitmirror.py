"""Git-Spiegel der Configs – gegen ein echtes, lokales Bare-Repository."""

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tesseract import gitmirror as gm
from tests.test_hosts import HOST


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    path = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(path)], check=True)
    return path


def _enable(client: TestClient, remote: Path, **git) -> dict:
    r = client.put(
        "/api/backups/config",
        json={"git": {"enabled": True, "url": remote.as_uri(), "auth": "none", **git}},
    )
    assert r.status_code == 200, r.text
    return r.json()["git"]


def _show(remote: Path, path: str) -> str:
    return _git("show", f"main:{path}", cwd=remote)


def test_mirror_hosts_and_nodes(auth_client: TestClient, remote: Path) -> None:
    assert auth_client.post("/api/hosts", json=HOST).status_code == 201
    git = _enable(auth_client, remote)
    assert git["enabled"] and git["token_set"] is False

    r = auth_client.post("/api/backups/git/sync")
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["ok"] and res["changed"] and res["commit"], res

    files = _git("ls-tree", "-r", "--name-only", "main", cwd=remote).split()
    assert "README.md" in files and "settings.json" in files and "ip-lists.json" in files
    host = json.loads(_show(remote, f"hosts/{HOST['domain'].lower()}.json"))
    assert host["upstream_host"] == HOST["upstream_host"]
    node = json.loads(_show(remote, "nodes/local.caddy.json"))
    assert "apps" in node
    settings = json.loads(_show(remote, "settings.json"))
    assert not any(k.endswith(("_enc", "_hash")) for k in settings)

    # nichts geändert → kein neuer Commit
    assert auth_client.post("/api/backups/git/sync").json()["changed"] is False
    assert len(_git("log", "--oneline", "main", cwd=remote).splitlines()) == 1

    # Host ändern → neuer Commit mit dem Audit-Eintrag als Nachricht
    host_id = auth_client.get("/api/hosts").json()[0]["id"]
    r = auth_client.put(f"/api/hosts/{host_id}", json={**HOST, "upstream_port": 9999})
    assert r.status_code == 200, r.text
    with auth_client.app.state.db.sessionmaker() as db:
        assert gm.due(db, auth_client.app.state.settings)
    assert auth_client.post("/api/backups/git/sync").json()["changed"] is True
    msg = _git("log", "-1", "--format=%s", "main", cwd=remote)
    assert "host_updated" in msg and HOST["domain"].lower() in msg
    path = f"hosts/{HOST['domain'].lower()}.json"
    assert json.loads(_show(remote, path))["upstream_port"] == 9999

    # Host löschen → Datei verschwindet
    assert auth_client.delete(f"/api/hosts/{host_id}").status_code in (200, 204)
    auth_client.post("/api/backups/git/sync")
    files = _git("ls-tree", "-r", "--name-only", "main", cwd=remote).split()
    assert f"hosts/{HOST['domain'].lower()}.json" not in files

    audit = auth_client.get("/api/audit", params={"q": "Git-Spiegel"}).json()
    entries = audit["entries"] if isinstance(audit, dict) else audit
    assert any(e["action"] == "git_mirrored" for e in entries)


def test_mirror_keeps_foreign_files_and_redacts(auth_client: TestClient, remote: Path, tmp_path):
    # Repository mit vorhandenem Inhalt (z. B. eigene Notizen)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True)
    (work / "NOTIZEN.md").write_text("bleibt\n")
    _git("-c", "user.name=x", "-c", "user.email=x@x", "add", ".", cwd=work)
    _git("-c", "user.name=x", "-c", "user.email=x@x", "commit", "-qm", "init", cwd=work)
    _git("push", "-q", "origin", "HEAD:main", cwd=work)

    with auth_client.app.state.db.sessionmaker() as db:
        from tesseract.services import CLOUDFLARE_CONTEXT, set_general

        box = auth_client.app.state.secretbox
        enc = box.encrypt(b"cf-geheim-123", CLOUDFLARE_CONTEXT)
        set_general(db, {"cloudflare_token_enc": enc, "metrics_token_hash": "abc"})
        db.commit()
    _enable(auth_client, remote)
    assert auth_client.post("/api/backups/git/sync").json()["ok"]
    assert _show(remote, "NOTIZEN.md") == "bleibt\n"
    assert "cf-geheim-123" not in _show(remote, "settings.json")
    assert "cf-geheim-123" not in _show(remote, "nodes/local.caddy.json")
    assert "abc" not in _show(remote, "settings.json")


def test_mirror_error_and_validation(auth_client: TestClient, tmp_path: Path) -> None:
    r = auth_client.put(
        "/api/backups/config",
        json={"git": {"enabled": True, "url": "https://user:pw@git.example.org/x.git"}},
    )
    assert r.status_code == 422 and "Token" in r.json()["detail"]
    r = auth_client.put("/api/backups/config", json={"git": {"enabled": True, "url": "ftp://x"}})
    assert r.status_code == 422
    r = auth_client.put(
        "/api/backups/config",
        json={"git": {"enabled": True, "url": "git@git.example.org:a/b.git", "ssh_key": "nö"}},
    )
    assert r.status_code == 422

    missing = tmp_path / "gibt-es-nicht.git"
    _enable(auth_client, missing, token="tok-123")
    res = auth_client.post("/api/backups/git/sync").json()
    assert res["ok"] is False and res["error"]
    cfg = auth_client.get("/api/backups/config").json()["git"]
    assert cfg["token_set"] and cfg["last"]["ok"] is False
    assert "tok-123" not in json.dumps(cfg)


def test_git_env_has_no_secret_in_args(tmp_path: Path) -> None:
    g = gm.Git(tmp_path / "w", "https://git.example.org/x.git", "main", token="tok", username="u")
    assert g.env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert "dTp0b2s=" in g.env["GIT_CONFIG_VALUE_0"]  # base64("u:tok")
    key = "-----BEGIN OPENSSH PRIVATE KEY-----"
    g2 = gm.Git(tmp_path / "w", "git@h:x.git", "main", ssh_key=key)
    keyfile = g2._keyfile
    assert keyfile and Path(keyfile).exists()
    assert "StrictHostKeyChecking" in g2.env["GIT_SSH_COMMAND"]
    g2.close()
    assert not Path(keyfile).exists()


def test_file_names() -> None:
    assert gm._file_name("*.home.example.org") == "_wildcard.home.example.org"
    assert gm._file_name("a/b") == "a_b"
