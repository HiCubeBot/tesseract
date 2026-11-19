"""Sicherungen (Phase 6): Einstellungen, sichern, Liste, Download, Test, Wiederherstellen."""

import asyncio
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from tesseract import audit
from tesseract import backup as b
from tesseract.deps import DB, AppSettings, Box, CurrentActor

router = APIRouter(prefix="/backups", tags=["backups"])

TargetName = Literal["local", "s3"]
MAX_UPLOAD = 512 * 1024 * 1024


class S3In(BaseModel):
    enabled: bool = False
    endpoint: str = Field("", max_length=500)
    bucket: str = Field("", max_length=255)
    region: str = Field("us-east-1", max_length=64)
    prefix: str = Field("tesseract", max_length=255)
    access_key: str = Field("", max_length=255)
    # None = unverändert, "" = löschen
    secret_key: str | None = Field(None, max_length=255)


class GitIn(BaseModel):
    enabled: bool = False
    url: str = Field("", max_length=500)
    branch: str = Field("main", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._/-]+$")
    auth: Literal["none", "token", "ssh"] = "token"
    username: str = Field("", max_length=100)
    # None = unverändert, "" = löschen
    token: str | None = Field(None, max_length=500)
    ssh_key: str | None = Field(None, max_length=10000)


class ConfigIn(BaseModel):
    schedule: Literal["off", "hourly", "daily", "weekly"] | None = None
    hour: int | None = Field(None, ge=0, le=23)
    weekday: int | None = Field(None, ge=0, le=6)
    timezone: str | None = Field(None, max_length=64)
    keep: int | None = Field(None, ge=1, le=1000)
    include_logs: bool | None = None
    passphrase: str | None = Field(None, max_length=500)
    local: bool | None = None
    s3: S3In | None = None
    git: GitIn | None = None


def _git_out(db) -> dict[str, Any]:
    from tesseract import gitmirror as gm

    g = gm.get_config(db)
    return {
        "enabled": g["enabled"],
        "url": g["url"],
        "branch": g["branch"],
        "auth": g["auth"],
        "username": g["username"],
        "token_set": bool(g["token_enc"]),
        "ssh_key_set": bool(g["ssh_key_enc"]),
        "last": g["last"],
    }


def _out(cfg: dict[str, Any], settings, db=None) -> dict[str, Any]:
    s3 = {k: v for k, v in cfg["s3"].items() if k != "secret_key_enc"}
    s3["secret_key_set"] = bool(cfg["s3"].get("secret_key_enc"))
    nxt = b.next_run(cfg, datetime.now(UTC))
    return {
        "schedule": cfg["schedule"],
        "hour": cfg["hour"],
        "weekday": cfg["weekday"],
        "timezone": cfg["timezone"],
        "keep": cfg["keep"],
        "include_logs": cfg["include_logs"],
        "passphrase_set": bool(cfg["passphrase_enc"]),
        "local": {"enabled": cfg["local"]["enabled"], "path": str(b.local_dir(settings))},
        "s3": s3,
        "last": cfg.get("last"),
        "last_test": cfg.get("last_test"),
        "next": nxt.isoformat() if nxt and cfg["passphrase_enc"] else None,
        "git": _git_out(db) if db is not None else None,
    }


@router.get("/config")
def get_config(db: DB, _: CurrentActor, settings: AppSettings) -> dict[str, Any]:
    return _out(b.get_config(db), settings, db)


@router.put("/config")
def put_config(
    body: ConfigIn, db: DB, box: Box, actor: CurrentActor, settings: AppSettings
) -> dict[str, Any]:
    cfg = b.get_config(db)
    value: dict[str, Any] = {
        k: v
        for k, v in body.model_dump(
            exclude_unset=True, exclude={"passphrase", "local", "s3", "git"}
        ).items()
        if v is not None
    }
    if "timezone" in value:
        from zoneinfo import ZoneInfo

        try:
            ZoneInfo(value["timezone"])
        except Exception as e:
            raise HTTPException(422, "Unbekannte Zeitzone") from e
    if body.passphrase is not None:
        if len(body.passphrase) < b.MIN_PASSPHRASE:
            raise HTTPException(422, f"Passphrase: mindestens {b.MIN_PASSPHRASE} Zeichen")
        value["passphrase_enc"] = box.encrypt(body.passphrase.encode(), b.PASSPHRASE_CONTEXT)
    if body.local is not None:
        value["local"] = {"enabled": body.local}
    if body.s3 is not None:
        s3 = body.s3
        if s3.enabled and not (s3.endpoint.startswith(("http://", "https://")) and s3.bucket):
            raise HTTPException(422, "S3: Adresse (http/https) und Bucket angeben")
        old = cfg["s3"].get("secret_key_enc", "")
        enc = (
            old
            if s3.secret_key is None
            else (box.encrypt(s3.secret_key.encode(), b.S3_CONTEXT) if s3.secret_key else "")
        )
        value["s3"] = {**s3.model_dump(exclude={"secret_key"}), "secret_key_enc": enc}
    git_changed: list[str] = []
    if body.git is not None:
        git_changed = _put_git(db, box, body.git)
    # Zeitplan neu gesetzt → ab jetzt zählen (nicht sofort nachholen)
    if value.get("schedule") and value["schedule"] != cfg["schedule"]:
        value["since"] = datetime.now(UTC).isoformat()
    cfg = b.set_config(db, value)
    changed = sorted(k for k in value if k != "since") + git_changed
    audit.record(
        db,
        actor=actor.name,
        action="settings_changed",
        target="Sicherungen",
        details={"changed": [c.replace("_enc", "") for c in changed]},
        ip=actor.ip,
    )
    db.commit()
    return _out(cfg, settings, db)


def _put_git(db, box, git: GitIn) -> list[str]:
    from tesseract import gitmirror as gm

    old = gm.get_config(db)
    value: dict[str, Any] = git.model_dump(exclude={"token", "ssh_key"})
    if git.enabled or git.url:
        try:
            value["url"] = gm.validate_url(git.url)
        except gm.MirrorError as e:
            raise HTTPException(422, str(e)) from e
    if git.token is not None:
        value["token_enc"] = box.encrypt(git.token.encode(), gm.TOKEN_CONTEXT) if git.token else ""
    if git.ssh_key is not None:
        key = git.ssh_key.strip()
        if key and "PRIVATE KEY" not in key:
            raise HTTPException(
                422, "SSH-Schlüssel: privater Schlüssel im OpenSSH- oder PEM-Format"
            )
        value["ssh_key_enc"] = box.encrypt(key.encode(), gm.SSH_CONTEXT) if key else ""
    # neue Adresse/Branch → beim nächsten Lauf neu spiegeln
    if value["url"] != old["url"] or value["branch"] != old["branch"]:
        value["digest"] = None
    changed = [f"git.{k.replace('_enc', '')}" for k, v in value.items() if old.get(k) != v]
    gm.set_config(db, value)
    return [c for c in changed if c != "git.digest"]


@router.post("/git/sync")
async def git_sync(db: DB, box: Box, actor: CurrentActor, settings: AppSettings) -> dict[str, Any]:
    """Jetzt spiegeln (auch ohne Änderung – prüft Zugang und Push)."""
    from tesseract import gitmirror as gm

    if not gm.get_config(db)["url"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Keine Adresse für den Git-Spiegel")
    return await asyncio.to_thread(gm.sync, db, settings, box, actor.name)


@router.post("")
async def backup_now(
    request: Request, db: DB, box: Box, actor: CurrentActor, settings: AppSettings
) -> dict[str, Any]:
    result = await asyncio.to_thread(
        b.run, db, settings, box, actor.name, request.app.state.backup_transport
    )
    if result["error"] and not result["targets"]:
        raise HTTPException(status.HTTP_409_CONFLICT, result["error"])
    return result


def _target(name: str, db, settings, box, request: Request):
    cfg = b.get_config(db)
    for t in b.targets(cfg, settings, box, request.app.state.backup_transport):
        if t.name == name:
            return t
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Ziel ist nicht eingeschaltet")


@router.get("")
def list_backups(
    request: Request, db: DB, box: Box, _: CurrentActor, settings: AppSettings
) -> list[dict[str, Any]]:
    """Alle Sicherungen aller Ziele, neueste zuerst."""
    out = []
    for t in b.targets(b.get_config(db), settings, box, request.app.state.backup_transport):
        try:
            out += [{"target": t.name, "name": n, "size": s} for n, s in t.list()]
        except (b.BackupError, OSError) as e:
            out.append({"target": t.name, "name": None, "size": 0, "error": str(e)})
    return sorted(out, key=lambda x: x["name"] or "", reverse=True)


@router.get("/{target}/{name}")
def download(
    target: TargetName,
    name: str,
    request: Request,
    db: DB,
    box: Box,
    actor: CurrentActor,
    settings: AppSettings,
) -> Response:
    data = _target(target, db, settings, box, request).get(b._safe(name))
    audit.record(db, actor=actor.name, action="backup_downloaded", target=name, ip=actor.ip)
    db.commit()
    return Response(
        data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


class FromTarget(BaseModel):
    target: TargetName
    name: str
    # leer = gespeicherte Passphrase
    passphrase: str = Field("", max_length=500)


def _load(body: FromTarget, request: Request, db, settings, box) -> tuple[bytes, str]:
    data = _target(body.target, db, settings, box, request).get(b._safe(body.name))
    try:
        phrase = body.passphrase or b.passphrase(b.get_config(db), box)
    except b.BackupError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    return data, phrase


@router.post("/test")
def test_backup(
    body: FromTarget, request: Request, db: DB, box: Box, actor: CurrentActor, settings: AppSettings
) -> dict[str, Any]:
    """Wiederherstellungstest: entschlüsseln und Datenbank prüfen, ohne etwas zu ändern."""
    data, phrase = _load(body, request, db, settings, box)
    result: dict[str, Any] = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "name": body.name,
        "ok": False,
        "error": None,
        "manifest": None,
    }
    try:
        result["manifest"] = b.inspect(data, phrase).manifest
        result["ok"] = True
    except b.BackupError as e:
        result["error"] = str(e)
    b.set_config(db, {"last_test": {k: v for k, v in result.items() if k != "manifest"}})
    audit.record(
        db,
        actor=actor.name,
        action="backup_tested",
        target=body.name,
        details={"ok": result["ok"], **({"error": result["error"]} if result["error"] else {})},
        ip=actor.ip,
    )
    db.commit()
    return result


async def _restore(request: Request, data: bytes, phrase: str, actor_name: str) -> dict[str, Any]:
    """Ersetzt den Stand des Controllers und verteilt die Config an alle Nodes."""
    from tesseract.db import run_migrations
    from tesseract.secretbox import load_secretbox
    from tesseract.services import apply_all

    app = request.app
    settings = app.state.settings
    try:
        item = await asyncio.to_thread(b.inspect, data, phrase)
    except b.BackupError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    database = app.state.db
    async with app.state.restore_lock:
        database.engine.dispose()
        try:
            await asyncio.to_thread(b.restore_files, settings, item)
        except b.BackupError as e:
            raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
        database.engine.dispose()
        await asyncio.to_thread(run_migrations, database.engine)
        app.state.secretbox = load_secretbox(settings)
        if getattr(app.state, "notifier", None):
            app.state.notifier.sender.box = app.state.secretbox
        with database.sessionmaker() as db:
            audit.record(
                db,
                actor=actor_name,
                action="backup_restored",
                target=item.manifest.get("created", ""),
                details={
                    "version": item.manifest.get("version"),
                    "counts": item.manifest.get("counts"),
                },
            )
            db.commit()
            errors = await asyncio.to_thread(apply_all, db, settings, app.state.caddy_transport)
            db.commit()
    return {"ok": True, "manifest": item.manifest, "apply_errors": errors}


@router.post("/restore")
async def restore_from_target(
    body: FromTarget, request: Request, db: DB, box: Box, actor: CurrentActor, settings: AppSettings
) -> dict[str, Any]:
    data, phrase = _load(body, request, db, settings, box)
    name = actor.name
    db.close()
    return await _restore(request, data, phrase, name)


@router.post("/restore/upload")
async def restore_upload(
    request: Request,
    db: DB,
    actor: CurrentActor,
    x_backup_passphrase: Annotated[str, Header()] = "",
) -> dict[str, Any]:
    """Sicherungsdatei als Rohdaten im Body (application/octet-stream), Passphrase im Header."""
    data = await request.body()
    if not data or len(data) > MAX_UPLOAD:
        raise HTTPException(422, "Leere oder zu große Datei")
    if not x_backup_passphrase:
        raise HTTPException(422, "Passphrase fehlt")
    name = actor.name
    db.close()  # Verbindung freigeben, bevor die Datei ersetzt wird
    return await _restore(request, data, x_backup_passphrase, name)
