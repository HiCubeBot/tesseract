"""Gesperrte IPs: auflisten, von Hand sperren, entsperren."""

import ipaddress
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from tesseract import audit
from tesseract.db.models import Ban, utcnow
from tesseract.deps import DB, AppSettings, CurrentActor
from tesseract.services import active_bans, apply_all

router = APIRouter(prefix="/bans", tags=["bans"])


class BanIn(BaseModel):
    ip: str
    # Stunden bis zum Ablauf; None = dauerhaft (bis zum Entsperren von Hand)
    hours: int | None = Field(24, ge=1, le=24 * 365 * 10)
    reason: str = Field("", max_length=255)

    @field_validator("ip")
    @classmethod
    def _ip(cls, v: str) -> str:
        try:
            return str(ipaddress.ip_network(v.strip(), strict=False))
        except ValueError as e:
            raise ValueError("Keine gültige IP bzw. kein Netz") from e


class BanOut(BaseModel):
    id: int
    ip: str
    created_at: datetime
    expires_at: datetime | None
    reason: str
    hits: int
    host: str
    created_by: str
    lifted_at: datetime | None
    lifted_by: str | None
    active: bool


def _out(b: Ban) -> BanOut:
    active = b.lifted_at is None and (b.expires_at is None or b.expires_at > utcnow())
    fields = {k: getattr(b, k) for k in BanOut.model_fields if k != "active"}
    return BanOut(**fields, active=active)


@router.get("")
def list_bans(db: DB, _: CurrentActor, all: bool = False) -> list[BanOut]:
    stmt = select(Ban).order_by(Ban.created_at.desc()).limit(500)
    bans = [_out(b) for b in db.scalars(stmt)]
    return bans if all else [b for b in bans if b.active]


@router.post("", status_code=status.HTTP_201_CREATED)
def ban(
    body: BanIn, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> BanOut:
    if body.ip in active_bans(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "Diese IP ist bereits gesperrt")
    b = Ban(
        ip=body.ip,
        expires_at=None if body.hours is None else utcnow() + timedelta(hours=body.hours),
        reason=body.reason or "von Hand gesperrt",
        created_by=actor.name,
    )
    db.add(b)
    audit.record(
        db,
        actor=actor.name,
        action="ip_banned",
        target=body.ip,
        details={"hours": body.hours or "dauerhaft", "reason": b.reason},
        ip=actor.ip,
    )
    db.commit()
    apply_all(db, settings, request.app.state.caddy_transport)
    db.commit()
    return _out(b)


@router.delete("/{ban_id}")
def lift(
    ban_id: int, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> BanOut:
    b = db.get(Ban, ban_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sperre nicht gefunden")
    if b.lifted_at is None:
        b.lifted_at, b.lifted_by = utcnow(), actor.name
        audit.record(db, actor=actor.name, action="ip_unbanned", target=b.ip, ip=actor.ip)
        db.commit()
        apply_all(db, settings, request.app.state.caddy_transport)
        db.commit()
    return _out(b)
