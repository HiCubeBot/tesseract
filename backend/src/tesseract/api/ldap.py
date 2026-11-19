"""Einstellungen und Abgleich für LDAP (Personen und Gruppen)."""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from tesseract import audit, ldapsync
from tesseract.deps import DB, AppSettings, Box, CurrentActor

router = APIRouter(prefix="/settings/ldap", tags=["settings"])


class LdapIn(BaseModel):
    enabled: bool = False
    url: str = Field("", max_length=500)
    starttls: bool = False
    bind_dn: str = Field("", max_length=500)
    # None = unverändert, "" = löschen
    bind_password: str | None = Field(None, max_length=500)
    user_base: str = Field("", max_length=500)
    user_filter: str = Field("(objectClass=person)", max_length=1000)
    attr_uid: str = Field("uid", max_length=64)
    attr_name: str = Field("cn", max_length=64)
    attr_mail: str = Field("mail", max_length=64)
    disabled_filter: str = Field("", max_length=1000)
    group_base: str = Field("", max_length=500)
    group_filter: str = Field(
        "(|(objectClass=groupOfNames)(objectClass=groupOfUniqueNames))", max_length=1000
    )
    attr_group_name: str = Field("cn", max_length=64)
    attr_member: str = Field("member", max_length=64)
    interval_minutes: int = Field(60, ge=5, le=10080)
    revoke_devices: bool = True


def _out(cfg: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in cfg.items() if k != "bind_password_enc"}
    out["bind_password_set"] = bool(cfg["bind_password_enc"])
    return out


@router.get("")
def get_ldap(db: DB, _: CurrentActor) -> dict[str, Any]:
    return _out(ldapsync.get_config(db))


@router.put("")
def put_ldap(body: LdapIn, db: DB, box: Box, actor: CurrentActor) -> dict[str, Any]:
    cfg = ldapsync.get_config(db)
    value = body.model_dump(exclude={"bind_password"})
    for k in ("url", "bind_dn", "user_base", "group_base"):
        value[k] = value[k].strip()
    if body.bind_password is not None:
        value["bind_password_enc"] = (
            box.encrypt(body.bind_password.encode(), ldapsync.SECRET_CONTEXT)
            if body.bind_password
            else ""
        )
    if value["enabled"]:
        if not value["url"].startswith(("ldap://", "ldaps://")):
            raise HTTPException(422, "Adresse muss mit ldap:// oder ldaps:// beginnen")
        if not value["user_base"]:
            raise HTTPException(422, "Suchbasis für Personen fehlt")
    cfg = ldapsync.set_config(db, value)
    audit.record(
        db,
        actor=actor.name,
        action="settings_changed",
        target="LDAP",
        ip=actor.ip,
        details={"enabled": value["enabled"], "url": value["url"]},
    )
    db.commit()
    return _out(cfg)


@router.post("/sync")
async def sync_now(
    request: Request,
    db: DB,
    box: Box,
    actor: CurrentActor,
    settings: AppSettings,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Jetzt abgleichen. `dry_run=true` zeigt nur, was sich ändern würde."""
    return await asyncio.to_thread(
        ldapsync.run,
        db,
        settings,
        box,
        actor.name,
        dry_run,
        request.app.state.caddy_transport,
        request.app.state.ldap_factory,
    )
