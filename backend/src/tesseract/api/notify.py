"""Einstellungen › Benachrichtigungen (Phase 5)."""

from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from tesseract import audit
from tesseract import notify as n
from tesseract.deps import DB, Box, CurrentActor
from tesseract.i18n import tr

router = APIRouter(prefix="/settings/notify", tags=["settings"])


class NtfyIn(BaseModel):
    enabled: bool = False
    url: str = Field("", max_length=500)
    # None = unverändert, "" = löschen
    token: str | None = Field(None, max_length=255)


class EmailIn(BaseModel):
    enabled: bool = False
    host: str = Field("", max_length=255)
    port: int = Field(587, ge=1, le=65535)
    security: Literal["starttls", "ssl", "none"] = "starttls"
    user: str = Field("", max_length=255)
    password: str | None = Field(None, max_length=255)
    sender: str = Field("", max_length=255)
    to: list[str] = Field(default_factory=list, max_length=20)


class WebhookIn(BaseModel):
    enabled: bool = False
    url: str = Field("", max_length=500)
    secret: str | None = Field(None, max_length=255)


class RuleIn(BaseModel):
    level: Literal["info", "warn", "critical"]
    channels: list[Literal["ntfy", "email", "webhook"]] = Field(default_factory=list)


class QuietIn(BaseModel):
    enabled: bool = True
    start: int = Field(22, ge=0, le=23)
    end: int = Field(7, ge=0, le=23)
    timezone: str = Field("Europe/Berlin", max_length=64)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        from zoneinfo import ZoneInfo

        try:
            ZoneInfo(v)
        except Exception as e:
            raise ValueError("Unbekannte Zeitzone") from e
        return v


class NotifyIn(BaseModel):
    ntfy: NtfyIn | None = None
    email: EmailIn | None = None
    webhook: WebhookIn | None = None
    rules: dict[str, RuleIn] | None = None
    quiet: QuietIn | None = None
    bundle_minutes: int | None = Field(None, ge=0, le=1440)
    # Sprache der Meldungen
    language: Literal["de", "en"] | None = None


def _url_ok(url: str) -> bool:
    return url.startswith(("https://", "http://"))


def _out(cfg: dict[str, Any], request: Request) -> dict[str, Any]:
    notifier = getattr(request.app.state, "notifier", None)
    return {
        "ntfy": {
            "enabled": cfg["ntfy"]["enabled"],
            "url": cfg["ntfy"]["url"],
            "token_set": bool(cfg["ntfy"]["token_enc"]),
        },
        "email": {
            **{k: v for k, v in cfg["email"].items() if k != "password_enc"},
            "password_set": bool(cfg["email"]["password_enc"]),
        },
        "webhook": {
            "enabled": cfg["webhook"]["enabled"],
            "url": cfg["webhook"]["url"],
            "secret_set": bool(cfg["webhook"]["secret_enc"]),
        },
        "rules": cfg["rules"],
        "quiet": cfg["quiet"],
        "bundle_minutes": cfg["bundle_minutes"],
        "language": cfg.get("language") or "de",
        "events": [
            {"id": ev, "title": title, "default_level": lvl}
            for ev, (title, lvl, _) in n.EVENTS.items()
        ],
        "errors": dict(notifier.errors) if notifier else {},
        "quiet_now": n.in_quiet(cfg),
    }


@router.get("")
def get_notify(request: Request, db: DB, _: CurrentActor) -> dict[str, Any]:
    return _out(n.get_config(db), request)


@router.put("")
def put_notify(
    body: NotifyIn, request: Request, db: DB, box: Box, actor: CurrentActor
) -> dict[str, Any]:
    cfg = n.get_config(db)
    value: dict[str, Any] = {}

    def secret(new: str | None, old: str) -> str:
        if new is None:
            return old
        return box.encrypt(new.strip().encode(), n.SECRET_CONTEXT) if new.strip() else ""

    if body.ntfy:
        if body.ntfy.enabled and not _url_ok(body.ntfy.url):
            raise HTTPException(422, "ntfy: Adresse des Themas, z. B. https://ntfy.sh/mein-thema")
        value["ntfy"] = {
            "enabled": body.ntfy.enabled,
            "url": body.ntfy.url.strip(),
            "token_enc": secret(body.ntfy.token, cfg["ntfy"]["token_enc"]),
        }
    if body.email:
        e = body.email
        if e.enabled and not (e.host and e.to):
            raise HTTPException(422, "E-Mail: Server und mindestens ein Empfänger nötig")
        value["email"] = {
            **e.model_dump(exclude={"password"}),
            "password_enc": secret(e.password, cfg["email"]["password_enc"]),
        }
    if body.webhook:
        if body.webhook.enabled and not _url_ok(body.webhook.url):
            raise HTTPException(422, "Webhook: Adresse mit http(s)://")
        value["webhook"] = {
            "enabled": body.webhook.enabled,
            "url": body.webhook.url.strip(),
            "secret_enc": secret(body.webhook.secret, cfg["webhook"]["secret_enc"]),
        }
    if body.rules is not None:
        unknown = set(body.rules) - set(n.EVENTS)
        if unknown:
            raise HTTPException(422, f"Unbekannte Ereignisse: {', '.join(sorted(unknown))}")
        value["rules"] = {**cfg["rules"], **{k: r.model_dump() for k, r in body.rules.items()}}
    if body.quiet:
        value["quiet"] = body.quiet.model_dump()
    if body.bundle_minutes is not None:
        value["bundle_minutes"] = body.bundle_minutes
    if body.language is not None:
        value["language"] = body.language
    cfg = n.set_config(db, value)
    audit.record(
        db,
        actor=actor.name,
        action="settings_changed",
        target="Benachrichtigungen",
        details={"changed": sorted(value)},
        ip=actor.ip,
    )
    db.commit()
    return _out(cfg, request)


class TestIn(BaseModel):
    channel: Literal["ntfy", "email", "webhook"]


@router.post("/test")
def test_notify(body: TestIn, request: Request, db: DB, _: CurrentActor) -> dict[str, Any]:
    cfg = n.get_config(db)
    if not cfg[body.channel]["enabled"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Kanal erst einschalten und speichern")
    lang = cfg.get("language") or "de"
    msg = n.Message(
        "test",
        "info",
        tr(lang, "Testmeldung"),
        [tr(lang, "Wenn das ankommt, klappen die Benachrichtigungen.")],
        lang=lang,
    )
    try:
        request.app.state.notifier.sender.send(body.channel, cfg, msg)
    except (httpx.HTTPError, OSError, ValueError) as e:
        return {"ok": False, "error": str(e)[:500]}
    return {"ok": True, "error": None}
