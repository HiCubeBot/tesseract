"""Phase 6: Verschlüsselte Backups des Controllers.

Eine Sicherung ist eine Datei `tesseract-JJJJMMTT-HHMMSS.tsbak`:

    TSBAK1\\n  JSON-Kopf (eine Zeile)  \\n  AES-256-GCM(ZIP)

- Der Schlüssel kommt per scrypt aus der Passphrase (Salz im Kopf). Ohne Passphrase ist
  nichts lesbar – auch nicht, welche Hosts es gibt.
- Das ZIP enthält einen konsistenten Schnappschuss der SQLite-Datenbank (Backup-API) und den
  Hauptschlüssel (`secret.key`), ohne den die verschlüsselten Werte in der DB (Schlüssel des
  Zwischenzertifikats, Tokens) unbrauchbar wären. Der Root-Schlüssel der CA liegt nie auf dem
  Controller und ist deshalb auch nie enthalten.
- Nodes brauchen keine Sicherung: Nach dem Wiederherstellen bekommen sie die Config neu.
"""

import base64
import hashlib
import hmac
import io
import json
import logging
import os
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from tesseract import __version__
from tesseract.config import Settings

log = logging.getLogger("tesseract.backup")

MAGIC = b"TSBAK1\n"
SUFFIX = ".tsbak"
NAME_RE = re.compile(r"^tesseract-\d{8}-\d{6}\.tsbak$")
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**15, 8, 1
MIN_PASSPHRASE = 12


class BackupError(Exception):
    pass


# ---------- Verschlüsselung ----------


def _key(passphrase: str, salt: bytes, n: int = SCRYPT_N, r: int = SCRYPT_R, p: int = SCRYPT_P):
    return Scrypt(salt=salt, length=32, n=n, r=r, p=p).derive(passphrase.encode())


def encrypt(payload: bytes, passphrase: str, meta: dict[str, Any]) -> bytes:
    salt, nonce = os.urandom(16), os.urandom(12)
    header = {
        **meta,
        "kdf": {"name": "scrypt", "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P},
        "salt": base64.b64encode(salt).decode(),
        "nonce": base64.b64encode(nonce).decode(),
    }
    head = json.dumps(header, separators=(",", ":")).encode()
    # Kopf als zusätzliche Daten mit authentifiziert: wer ihn ändert, macht die Datei unlesbar
    ct = AESGCM(_key(passphrase, salt)).encrypt(nonce, payload, head)
    return MAGIC + head + b"\n" + ct


def read_header(data: bytes) -> tuple[dict[str, Any], bytes, bytes]:
    if not data.startswith(MAGIC):
        raise BackupError("Keine Tesseract-Sicherung (falsches Format)")
    head, sep, ct = data[len(MAGIC) :].partition(b"\n")
    if not sep:
        raise BackupError("Sicherung ist beschädigt")
    try:
        return json.loads(head), head, ct
    except ValueError as e:
        raise BackupError("Sicherung ist beschädigt") from e


def decrypt(data: bytes, passphrase: str) -> tuple[dict[str, Any], bytes]:
    header, head, ct = read_header(data)
    kdf = header.get("kdf", {})
    try:
        key = _key(
            passphrase,
            base64.b64decode(header["salt"]),
            int(kdf.get("n", SCRYPT_N)),
            int(kdf.get("r", SCRYPT_R)),
            int(kdf.get("p", SCRYPT_P)),
        )
        return header, AESGCM(key).decrypt(base64.b64decode(header["nonce"]), ct, head)
    except Exception as e:  # InvalidTag, falsches Base64 …
        raise BackupError("Passphrase falsch oder Sicherung beschädigt") from e


# ---------- Inhalt ----------


def _db_path(settings: Settings) -> Path:
    url = settings.resolved_database_url
    if not url.startswith("sqlite:///"):
        raise BackupError("Sicherungen gehen nur mit SQLite")
    return Path(url.removeprefix("sqlite:///"))


def _secret_key_bytes(settings: Settings) -> bytes:
    if settings.secret_key:
        return settings.secret_key.strip().encode()
    path = Path(settings.data_dir) / "secret.key"
    return path.read_bytes().strip() if path.exists() else b""


def snapshot(settings: Settings, include_logs: bool = False) -> tuple[bytes, dict[str, Any]]:
    """ZIP mit DB-Schnappschuss, Hauptschlüssel und Inhaltsangabe."""
    src = sqlite3.connect(_db_path(settings))
    with tempfile.TemporaryDirectory() as tmp:
        copy_path = Path(tmp) / "tesseract.db"
        dst = sqlite3.connect(copy_path)
        try:
            src.backup(dst)  # konsistent, auch während der Controller schreibt
            if not include_logs:
                dst.execute("DELETE FROM log_entries")
                dst.commit()
                dst.execute("VACUUM")
            counts = {
                t: dst.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: S608
                for t in ("hosts", "persons", "devices", "nodes", "audit_log", "log_entries")
            }
        finally:
            dst.close()
            src.close()
        manifest = {
            "version": __version__,
            "created": datetime.now(UTC).isoformat(timespec="seconds"),
            "logs": include_logs,
            "counts": counts,
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copy_path, "tesseract.db")
            z.writestr("secret.key", _secret_key_bytes(settings))
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
        return buf.getvalue(), manifest


def create(settings: Settings, passphrase: str, include_logs: bool = False) -> tuple[str, bytes]:
    payload, manifest = snapshot(settings, include_logs)
    name = f"tesseract-{datetime.now(UTC):%Y%m%d-%H%M%S}{SUFFIX}"
    meta = {"app": "tesseract", "version": __version__, "created": manifest["created"]}
    return name, encrypt(payload, passphrase, meta)


@dataclass
class Inspected:
    header: dict[str, Any]
    manifest: dict[str, Any]
    db: bytes
    secret_key: bytes


def inspect(data: bytes, passphrase: str) -> Inspected:
    """Entschlüsseln und prüfen (Wiederherstellungstest) – ohne etwas zu ändern."""
    header, payload = decrypt(data, passphrase)
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            db = z.read("tesseract.db")
            key = z.read("secret.key")
            manifest = json.loads(z.read("manifest.json"))
    except (KeyError, zipfile.BadZipFile, ValueError) as e:
        raise BackupError("Inhalt der Sicherung ist unvollständig") from e
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "check.db"
        p.write_bytes(db)
        con = sqlite3.connect(p)
        try:
            ok = con.execute("PRAGMA integrity_check").fetchone()[0]
            con.execute("SELECT COUNT(*) FROM alembic_version").fetchone()
        except sqlite3.DatabaseError as e:
            raise BackupError(f"Datenbank in der Sicherung ist beschädigt: {e}") from e
        finally:
            con.close()
    if ok != "ok":
        raise BackupError(f"Datenbank in der Sicherung ist beschädigt: {ok}")
    return Inspected(header, manifest, db, key)


def restore_files(settings: Settings, item: Inspected) -> None:
    """Ersetzt Datenbank und Hauptschlüssel. Der Aufrufer muss vorher alle DB-Verbindungen
    schließen (engine.dispose) und danach Migrationen ausführen."""
    db_path = _db_path(settings)
    if settings.secret_key:
        if item.secret_key and item.secret_key != settings.secret_key.strip().encode():
            raise BackupError(
                "Die Sicherung gehört zu einem anderen Hauptschlüssel als TESSERACT_SECRET_KEY – "
                "dort den Schlüssel aus der Sicherung eintragen oder die Variable entfernen"
            )
    else:
        key_path = Path(settings.data_dir) / "secret.key"
        if item.secret_key:
            key_path.write_bytes(item.secret_key)
            os.chmod(key_path, 0o600)
    for suffix in ("-wal", "-shm"):
        Path(str(db_path) + suffix).unlink(missing_ok=True)
    tmp = db_path.with_suffix(".restore")
    tmp.write_bytes(item.db)
    tmp.replace(db_path)


# ---------- Ziele ----------


class LocalTarget:
    name = "local"

    def __init__(self, path: Path) -> None:
        self.path = path

    def put(self, name: str, data: bytes) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        tmp = self.path / (name + ".part")
        tmp.write_bytes(data)
        os.chmod(tmp, 0o600)
        tmp.replace(self.path / name)

    def list(self) -> list[tuple[str, int]]:
        if not self.path.is_dir():
            return []
        return sorted(
            (p.name, p.stat().st_size) for p in self.path.iterdir() if NAME_RE.match(p.name)
        )

    def get(self, name: str) -> bytes:
        return (self.path / _safe(name)).read_bytes()

    def delete(self, name: str) -> None:
        (self.path / _safe(name)).unlink(missing_ok=True)


def _safe(name: str) -> str:
    if not NAME_RE.match(name):
        raise BackupError("Ungültiger Name einer Sicherung")
    return name


class S3Target:
    """Minimaler S3-Client (AWS Signature V4) – reicht für MinIO, Garage, Backblaze, AWS …"""

    name = "s3"

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        prefix: str = "",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region or "us-east-1"
        self.prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        self.transport = transport

    def _request(
        self, method: str, key: str = "", body: bytes = b"", query: dict[str, str] | None = None
    ) -> httpx.Response:
        query = query or {}
        host = urlsplit(self.endpoint).netloc
        path = f"/{self.bucket}" + (f"/{quote(key, safe='/')}" if key else "")
        now = datetime.now(UTC)
        amz_date, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(body).hexdigest()
        canonical_query = "&".join(
            f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(query.items())
        )
        headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
        signed = ";".join(sorted(headers))
        canonical = "\n".join(
            [
                method,
                path,
                canonical_query,
                "".join(f"{k}:{headers[k]}\n" for k in sorted(headers)),
                signed,
                payload_hash,
            ]
        )
        scope = f"{day}/{self.region}/s3/aws4_request"
        to_sign = "\n".join(
            ["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()]
        )
        k = f"AWS4{self.secret_key}".encode()
        for part in (day, self.region, "s3", "aws4_request"):
            k = hmac.new(k, part.encode(), hashlib.sha256).digest()
        sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
        headers["authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{scope}, "
            f"SignedHeaders={signed}, Signature={sig}"
        )
        url = self.endpoint + path + (f"?{canonical_query}" if canonical_query else "")
        with httpx.Client(timeout=120.0, transport=self.transport) as c:
            r = c.request(method, url, content=body, headers=headers)
        if r.status_code >= 300:
            raise BackupError(f"S3 {r.status_code}: {_s3_error(r.text)}")
        return r

    def put(self, name: str, data: bytes) -> None:
        self._request("PUT", self.prefix + name, data)

    def list(self) -> list[tuple[str, int]]:
        r = self._request("GET", query={"list-type": "2", "prefix": self.prefix})
        out = []
        for key, size in re.findall(
            r"<Key>([^<]+)</Key>.*?<Size>(\d+)</Size>", r.text, flags=re.DOTALL
        ):
            name = key[len(self.prefix) :]
            if NAME_RE.match(name):
                out.append((name, int(size)))
        return sorted(out)

    def get(self, name: str) -> bytes:
        return self._request("GET", self.prefix + _safe(name)).content

    def delete(self, name: str) -> None:
        self._request("DELETE", self.prefix + _safe(name))


def _s3_error(text: str) -> str:
    m = re.search(r"<Message>([^<]+)</Message>", text)
    return m.group(1) if m else text[:300]


# ---------- Zeitplan ----------


def _slot(cfg: dict[str, Any], now: datetime) -> tuple[datetime, timedelta] | None:
    """Letzter planmäßiger Zeitpunkt <= now und der Abstand zwischen zwei Läufen."""
    from zoneinfo import ZoneInfo

    schedule = cfg.get("schedule", "off")
    if schedule not in ("hourly", "daily", "weekly"):
        return None
    tz = ZoneInfo(cfg.get("timezone") or "Europe/Berlin")
    local = now.astimezone(tz)
    if schedule == "hourly":
        return local.replace(minute=0, second=0, microsecond=0), timedelta(hours=1)
    slot = local.replace(hour=int(cfg.get("hour", 3)), minute=0, second=0, microsecond=0)
    step = timedelta(days=7 if schedule == "weekly" else 1)
    if schedule == "weekly":
        slot -= timedelta(days=(slot.weekday() - int(cfg.get("weekday", 6))) % 7)
    if slot > local:
        slot -= step
    return slot, step


def is_due(cfg: dict[str, Any], last: datetime | None, since: datetime, now: datetime) -> bool:
    """Fällig, wenn seit dem Einschalten (`since`) ein Zeitpunkt erreicht und noch nicht
    gesichert wurde. Verpasste Läufe (Controller war aus) werden einmal nachgeholt."""
    s = _slot(cfg, now)
    if s is None:
        return False
    slot, _ = s
    return slot >= since and (last is None or last < slot)


def next_run(cfg: dict[str, Any], now: datetime) -> datetime | None:
    s = _slot(cfg, now)
    return None if s is None else (s[0] + s[1]).astimezone(UTC)


# ---------- Einstellungen & Ablauf ----------

DEFAULTS: dict[str, Any] = {
    "schedule": "off",  # off | hourly | daily | weekly
    "hour": 3,
    "weekday": 6,  # 0 = Montag … 6 = Sonntag
    "timezone": "Europe/Berlin",
    "keep": 14,
    "include_logs": False,
    "passphrase_enc": "",
    # ab wann der Zeitplan gilt (verhindert, dass beim Einschalten sofort gesichert wird)
    "since": None,
    "local": {"enabled": True},
    "s3": {
        "enabled": False,
        "endpoint": "",
        "bucket": "",
        "region": "us-east-1",
        "prefix": "tesseract",
        "access_key": "",
        "secret_key_enc": "",
    },
    "last": None,  # {"at", "ok", "name", "size", "targets", "error"}
    "last_test": None,  # {"at", "ok", "name", "error"}
}
PASSPHRASE_CONTEXT = "backup-passphrase"
S3_CONTEXT = "backup-s3-secret"


def get_config(db) -> dict[str, Any]:
    from tesseract.db.models import Setting

    row = db.get(Setting, "backup")
    cfg = json.loads(json.dumps(DEFAULTS))
    for k, v in (row.value if row else {}).items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def set_config(db, value: dict[str, Any]) -> dict[str, Any]:
    from tesseract.db.models import Setting

    cfg = {**get_config(db), **value}
    row = db.get(Setting, "backup")
    if row is None:
        db.add(Setting(key="backup", value=cfg))
    else:
        row.value = cfg
    return cfg


def local_dir(settings: Settings) -> Path:
    return Path(settings.backup_dir) if settings.backup_dir else Path(settings.data_dir) / "backups"


def targets(cfg: dict[str, Any], settings: Settings, box, transport=None) -> list:
    out: list = []
    if cfg["local"].get("enabled"):
        out.append(LocalTarget(local_dir(settings)))
    s3 = cfg["s3"]
    if s3.get("enabled") and s3.get("endpoint") and s3.get("bucket"):
        secret = (
            box.decrypt(s3["secret_key_enc"], S3_CONTEXT).decode()
            if s3.get("secret_key_enc")
            else ""
        )
        out.append(
            S3Target(
                s3["endpoint"],
                s3["bucket"],
                s3.get("access_key", ""),
                secret,
                s3.get("region", "us-east-1"),
                s3.get("prefix", ""),
                transport,
            )
        )
    return out


def passphrase(cfg: dict[str, Any], box) -> str:
    if not cfg.get("passphrase_enc"):
        raise BackupError("Erst eine Passphrase für die Sicherungen festlegen")
    return box.decrypt(cfg["passphrase_enc"], PASSPHRASE_CONTEXT).decode()


def run(db, settings: Settings, box, actor: str = "system", transport=None) -> dict[str, Any]:
    """Sichern, an alle Ziele schicken, alte Sicherungen aufräumen. Ergebnis wird gespeichert
    und protokolliert; Fehler eines Ziels verhindern nicht die anderen."""
    from tesseract import audit

    cfg = get_config(db)
    result: dict[str, Any] = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "ok": False,
        "name": None,
        "size": 0,
        "targets": [],
        "error": None,
    }
    try:
        name, data = create(settings, passphrase(cfg, box), bool(cfg.get("include_logs")))
        result.update(name=name, size=len(data))
        dests = targets(cfg, settings, box, transport)
        if not dests:
            raise BackupError("Kein Ziel eingeschaltet")
        errors = []
        for t in dests:
            try:
                t.put(name, data)
                prune(t, int(cfg.get("keep") or 14))
                result["targets"].append(t.name)
            except (BackupError, OSError, httpx.HTTPError) as e:
                errors.append(f"{t.name}: {e}")
        result["ok"] = bool(result["targets"]) and not errors
        result["error"] = "; ".join(errors) or None
    except (BackupError, OSError, sqlite3.Error) as e:
        result["error"] = str(e)
    set_config(db, {"last": result})
    audit.record(
        db,
        actor=actor,
        action="backup_created" if result["ok"] else "backup_failed",
        target=result["name"] or "",
        details={k: result[k] for k in ("size", "targets", "error") if result[k]},
    )
    db.commit()
    if not result["ok"]:
        log.error("Sicherung fehlgeschlagen: %s", result["error"])
    return result


def prune(target, keep: int) -> list[str]:
    names = [n for n, _ in target.list()]
    old = names[: max(0, len(names) - max(1, keep))]
    for n in old:
        target.delete(n)
    return old


async def watch(app, interval: float = 60.0) -> None:
    """Hintergrund: Zeitplan prüfen und bei Fälligkeit sichern."""
    import asyncio

    while True:
        try:
            with app.state.db.sessionmaker() as db:
                cfg = get_config(db)
                last = cfg.get("last") or {}
                last_at = datetime.fromisoformat(last["at"]) if last.get("at") else None
                since = datetime.fromisoformat(cfg["since"]) if cfg.get("since") else None
                now = datetime.now(UTC)
                if since and cfg.get("passphrase_enc") and is_due(cfg, last_at, since, now):
                    await asyncio.to_thread(run, db, app.state.settings, app.state.secretbox)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover – die Schleife darf nie sterben
            log.exception("Sicherung: Fehler im Zeitplan")
        await asyncio.sleep(interval)
