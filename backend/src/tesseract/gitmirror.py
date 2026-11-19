"""Git-Spiegel der Configs (Backup-Ziel).

Neben den verschlüsselten Sicherungen schreibt der Controller den Stand der Konfiguration
lesbar in ein Git-Repository – jede Änderung ein Commit. So lässt sich nachvollziehen, wann
sich was geändert hat, und eine Config im Notfall von Hand wiederherstellen.

Inhalt (ohne Geheimnisse – keine Schlüssel, Tokens, Passwort-Hashes, keine Personen):

    README.md
    settings.json            Einstellungen der Oberfläche
    ip-lists.json            Benannte IP-Listen
    hosts/<domain>.json      Einstellungen pro Host (wie im Verlauf)
    nodes/<name>.caddy.json  Caddy-Config pro Node (Schlüssel geschwärzt, ohne IP-Sperren)

Der Spiegel geht nur in eine Richtung: Änderungen im Repository werden beim nächsten Lauf
überschrieben. Gebraucht wird das `git`-Programm (im Image enthalten), für SSH `ssh`.
"""

import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.config import Settings

log = logging.getLogger("tesseract.gitmirror")

TOKEN_CONTEXT = "gitmirror-token"
SSH_CONTEXT = "gitmirror-ssh-key"
MANAGED = ("README.md", "settings.json", "ip-lists.json", "hosts", "nodes")
# Einstellungen, die nie in den Spiegel gehören
SECRET_SUFFIXES = ("_enc", "_hash")
TIMEOUT = 120

README = """# Tesseract – Config-Spiegel

Automatisch geschrieben vom Tesseract-Controller. Jede Änderung ist ein Commit.
Änderungen hier werden beim nächsten Lauf überschrieben.

- `settings.json` – Einstellungen der Oberfläche (ohne Geheimnisse)
- `ip-lists.json` – benannte IP-Listen
- `hosts/<domain>.json` – Einstellungen pro Host
- `nodes/<name>.caddy.json` – Caddy-Config pro Node; Schlüssel und Tokens geschwärzt,
  ohne die (häufig wechselnden) IP-Sperren

Nicht enthalten: Personen, Geräte, Schlüssel, Tokens. Für eine vollständige Wiederherstellung
die verschlüsselten Sicherungen (`.tsbak`) verwenden.
"""


class MirrorError(Exception):
    pass


# ---------- Export ----------


def _dump(data: Any) -> bytes:
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True, default=str)
    return (text + "\n").encode()


def _file_name(name: str) -> str:
    """Domain/Node-Name als Dateiname (Wildcards: `*.x` → `_wildcard.x`)."""
    name = name.replace("*", "_wildcard")
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) or "_"


def export(db: Session, settings: Settings) -> dict[str, bytes]:
    """Alle Dateien des Spiegels (Pfad → Inhalt)."""
    from tesseract.caddy.config import redact
    from tesseract.db.models import Host, IpList, Node
    from tesseract.services import get_general, node_config, snapshot

    files: dict[str, bytes] = {"README.md": README.encode()}
    general = {k: v for k, v in get_general(db).items() if not k.endswith(SECRET_SUFFIXES)}
    files["settings.json"] = _dump(general)
    files["ip-lists.json"] = _dump(
        [
            {"name": li.name, "description": li.description, "entries": li.entries}
            for li in db.scalars(select(IpList).order_by(IpList.name))
        ]
    )
    for host in db.scalars(select(Host).order_by(Host.domain)):
        files[f"hosts/{_file_name(host.domain)}.json"] = _dump(snapshot(host))
    for node in db.scalars(select(Node).order_by(Node.name)):
        if node.is_agent and not node.joined:
            continue
        config = redact(node_config(db, node, settings, bans=False))
        files[f"nodes/{_file_name(node.name)}.caddy.json"] = _dump(config)
    return files


def digest(files: dict[str, bytes]) -> str:
    import hashlib

    h = hashlib.sha256()
    for path in sorted(files):
        h.update(path.encode() + b"\0" + files[path] + b"\0")
    return h.hexdigest()


# ---------- Git ----------


class Git:
    """Dünne Hülle um das `git`-Programm mit Zugangsdaten nur in der Umgebung (nicht in
    der Kommandozeile, nicht in .git/config)."""

    def __init__(
        self,
        workdir: Path,
        url: str,
        branch: str,
        token: str = "",
        username: str = "",
        ssh_key: str = "",
        known_hosts: Path | None = None,
    ) -> None:
        if not shutil.which("git"):
            raise MirrorError("Das Programm „git“ ist nicht installiert")
        self.workdir = workdir
        self.url = url
        self.branch = branch
        self.env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Tesseract",
            "GIT_AUTHOR_EMAIL": "tesseract@localhost",
            "GIT_COMMITTER_NAME": "Tesseract",
            "GIT_COMMITTER_EMAIL": "tesseract@localhost",
        }
        self._keyfile: str | None = None
        if token:
            basic = base64.b64encode(f"{username or 'git'}:{token}".encode()).decode()
            self.env.update(
                GIT_CONFIG_COUNT="1",
                GIT_CONFIG_KEY_0="http.extraHeader",
                GIT_CONFIG_VALUE_0=f"Authorization: Basic {basic}",
            )
        if ssh_key:
            fd, self._keyfile = tempfile.mkstemp(prefix="tesseract-git-")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(ssh_key.strip() + "\n")
            os.chmod(self._keyfile, 0o600)
            kh = known_hosts or (workdir.parent / "git-mirror-known_hosts")
            self.env["GIT_SSH_COMMAND"] = (
                f'ssh -i "{self._keyfile}" -o IdentitiesOnly=yes -o BatchMode=yes '
                f'-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile="{kh}"'
            )

    def close(self) -> None:
        if self._keyfile:
            Path(self._keyfile).unlink(missing_ok=True)
            self._keyfile = None

    def __enter__(self) -> "Git":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def run(self, *args: str, cwd: Path | None = None, check: bool = True) -> str:
        try:
            p = subprocess.run(  # noqa: S603 – feste Argumente, kein Shell
                ["git", *args],
                cwd=cwd or self.workdir,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
        except subprocess.TimeoutExpired as e:
            raise MirrorError(f"git {args[0]}: Zeitüberschreitung") from e
        if check and p.returncode != 0:
            msg = (p.stderr or p.stdout).strip().splitlines()
            raise MirrorError(f"git {args[0]}: {msg[-1] if msg else p.returncode}")
        return p.stdout

    def remote_has_branch(self) -> bool:
        out = self.run("ls-remote", "--heads", self.url, self.branch, cwd=self.workdir.parent)
        return bool(out.strip())

    def prepare(self) -> None:
        """Arbeitskopie auf den Stand des entfernten Branches bringen (oder neu anlegen)."""
        self.workdir.mkdir(parents=True, exist_ok=True)
        if not (self.workdir / ".git").is_dir():
            self.run("init", "-q")
        self.run("remote", "remove", "origin", check=False)
        self.run("remote", "add", "origin", self.url)
        if self.remote_has_branch():
            self.run("fetch", "-q", "--depth", "1", "origin", self.branch)
            self.run("checkout", "-q", "-B", self.branch, "FETCH_HEAD")
            self.run("reset", "-q", "--hard", "FETCH_HEAD")
        else:
            # leeres Repository oder neuer Branch: ohne Vorgeschichte anfangen
            self.run("checkout", "-q", "--orphan", self.branch, check=False)
            self.run("rm", "-rq", "--cached", ".", check=False)
        self.run("clean", "-qfdx")


def write_files(workdir: Path, files: dict[str, bytes]) -> None:
    """Verwaltete Dateien ersetzen; was nicht mehr exportiert wird, verschwindet."""
    for name in MANAGED:
        p = workdir / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    for rel, data in files.items():
        p = workdir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def commit_message(db: Session, since: datetime | None) -> str:
    """Betreff + die Änderungen laut Audit-Log seit dem letzten Spiegeln."""
    from tesseract.db.models import AuditEntry

    if since is None:
        return "Tesseract: erster Stand"
    skip = ("login", "backup_", "git_", "node_online", "config_applied", "ip_", "enrollment_code")
    stmt = (
        select(AuditEntry)
        .where(AuditEntry.created_at > since)
        .order_by(AuditEntry.id.desc())
        .limit(200)
    )
    lines = []
    for e in reversed(list(db.scalars(stmt))):
        if e.action.startswith(skip):
            continue
        lines.append(f"- {e.actor}: {e.action} {e.target}".rstrip())
    subject = "Tesseract: Config geändert"
    if len(lines) == 1:
        subject = f"Tesseract: {lines[0][2:]}"[:72]
    body = "\n".join(lines[-30:])
    return subject + ("\n\n" + body if body and len(lines) > 1 else "")


# ---------- Einstellungen & Ablauf ----------

DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "url": "",
    "branch": "main",
    # Anmeldung: none | token (HTTPS) | ssh (Deploy-Key)
    "auth": "token",
    "username": "",
    "token_enc": "",
    "ssh_key_enc": "",
    "last": None,  # {"at", "ok", "commit", "error", "changed"}
    "digest": None,  # Stand des zuletzt gespiegelten Exports
    "synced_at": None,
}


def get_config(db: Session) -> dict[str, Any]:
    from tesseract.db.models import Setting

    row = db.get(Setting, "gitmirror")
    return {**DEFAULTS, **(row.value if row else {})}


def set_config(db: Session, value: dict[str, Any]) -> dict[str, Any]:
    from tesseract.db.models import Setting

    cfg = {**get_config(db), **value}
    row = db.get(Setting, "gitmirror")
    if row is None:
        db.add(Setting(key="gitmirror", value=cfg))
    else:
        row.value = cfg
    return cfg


def validate_url(url: str) -> str:
    url = url.strip()
    if not re.match(r"^(https?://|ssh://|file://|[\w.-]+@[\w.-]+:)", url):
        raise MirrorError("Adresse: https://…, ssh://… oder git@host:pfad.git")
    if re.match(r"^https?://[^/]*@", url):
        raise MirrorError("Zugangsdaten nicht in die Adresse schreiben – Feld „Token“ nutzen")
    return url


def workdir(settings: Settings) -> Path:
    return Path(settings.data_dir) / "git-mirror"


def _git(cfg: dict[str, Any], settings: Settings, box) -> Git:
    token = ssh_key = ""
    if cfg["auth"] == "token" and cfg.get("token_enc"):
        token = box.decrypt(cfg["token_enc"], TOKEN_CONTEXT).decode()
    if cfg["auth"] == "ssh" and cfg.get("ssh_key_enc"):
        ssh_key = box.decrypt(cfg["ssh_key_enc"], SSH_CONTEXT).decode()
    return Git(
        workdir(settings),
        cfg["url"],
        cfg.get("branch") or "main",
        token=token,
        username=cfg.get("username", ""),
        ssh_key=ssh_key,
    )


def sync(db: Session, settings: Settings, box, actor: str = "system") -> dict[str, Any]:
    """Export schreiben, committen, pushen. Ergebnis wird gespeichert."""
    from tesseract import audit

    cfg = get_config(db)
    files = export(db, settings)
    dig = digest(files)
    now = datetime.now(UTC)
    result: dict[str, Any] = {
        "at": now.isoformat(timespec="seconds"),
        "ok": False,
        "commit": None,
        "changed": False,
        "error": None,
    }
    since = datetime.fromisoformat(cfg["synced_at"]) if cfg.get("synced_at") else None
    try:
        if not cfg.get("url"):
            raise MirrorError("Keine Adresse eingetragen")
        with _git(cfg, settings, box) as git:
            git.prepare()
            write_files(git.workdir, files)
            git.run("add", "-A")
            if git.run("status", "--porcelain").strip():
                msg = commit_message(db, since)
                git.run("commit", "-q", "-m", msg)
                git.run("push", "-q", "origin", f"HEAD:refs/heads/{git.branch}")
                result["changed"] = True
            result["commit"] = git.run("rev-parse", "--short", "HEAD", check=False).strip() or None
        result["ok"] = True
    except (MirrorError, OSError) as e:
        result["error"] = str(e)
    value: dict[str, Any] = {"last": result}
    if result["ok"]:
        value.update(digest=dig, synced_at=now.isoformat())
    set_config(db, value)
    if result["changed"] or not result["ok"] or actor != "system":
        audit.record(
            db,
            actor=actor,
            action="git_mirrored" if result["ok"] else "backup_failed",
            target="Git-Spiegel",
            details={
                **({"commit": result["commit"]} if result["commit"] else {}),
                **({"error": f"Git-Spiegel: {result['error']}"} if result["error"] else {}),
            },
        )
    db.commit()
    if not result["ok"]:
        log.error("Git-Spiegel fehlgeschlagen: %s", result["error"])
    return result


def due(db: Session, settings: Settings) -> bool:
    """Spiegeln, wenn eingeschaltet und sich der Export geändert hat."""
    cfg = get_config(db)
    if not (cfg.get("enabled") and cfg.get("url")):
        return False
    return digest(export(db, settings)) != cfg.get("digest")


async def watch(app, interval: float = 30.0) -> None:
    """Hintergrund: Änderungen erkennen und spiegeln. Nach einem Fehler erst nach 10 Minuten
    erneut versuchen, damit ein falsches Passwort nicht ständig Meldungen erzeugt."""
    import asyncio

    while True:
        try:
            with app.state.db.sessionmaker() as db:
                cfg = get_config(db)
                last = cfg.get("last") or {}
                wait = False
                if last and not last.get("ok") and last.get("at"):
                    age = datetime.now(UTC) - datetime.fromisoformat(last["at"])
                    wait = age.total_seconds() < 600
                if not wait and await asyncio.to_thread(due, db, app.state.settings):
                    await asyncio.to_thread(sync, db, app.state.settings, app.state.secretbox)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover – die Schleife darf nie sterben
            log.exception("Git-Spiegel: Fehler im Hintergrund")
        await asyncio.sleep(interval)
