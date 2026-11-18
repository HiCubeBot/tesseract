import csv
import io
import json
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import Select, or_, select

from tesseract import audit
from tesseract.db.models import Admin, AuditEntry
from tesseract.deps import DB, CurrentActor

router = APIRouter(prefix="/audit", tags=["audit"])

# Wer hat es getan? admin = angemeldete Admins, system = Controller selbst,
# guest = Gäste der Einladungsseite, agent = Agents der Nodes
Kind = Literal["", "admin", "system", "guest", "agent"]


class AuditOut(BaseModel):
    id: int
    created_at: datetime
    actor: str
    action: str
    target: str
    details: dict[str, Any]
    ip: str | None
    hash: str | None


def _filtered(db, q: str, kind: str) -> Select:
    stmt = select(AuditEntry)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                AuditEntry.actor.ilike(like),
                AuditEntry.action.ilike(like),
                AuditEntry.target.ilike(like),
            )
        )
    if kind == "admin":
        stmt = stmt.where(AuditEntry.actor.in_(select(Admin.username)))
    elif kind == "system":
        stmt = stmt.where(AuditEntry.actor == "system")
    elif kind == "guest":
        stmt = stmt.where(AuditEntry.actor == "Gast")
    elif kind == "agent":
        stmt = stmt.where(AuditEntry.actor == "agent")
    return stmt


@router.get("")
def list_audit(
    db: DB,
    _: CurrentActor,
    q: str = "",
    kind: Kind = "",
    limit: int = Query(100, ge=1, le=500),
    before_id: int | None = None,
) -> list[AuditOut]:
    audit.seal(db)
    stmt = _filtered(db, q, kind).order_by(AuditEntry.id.desc()).limit(limit)
    if before_id:
        stmt = stmt.where(AuditEntry.id < before_id)
    return [AuditOut.model_validate(e, from_attributes=True) for e in db.scalars(stmt)]


@router.get("/verify")
def verify(db: DB, _: CurrentActor) -> dict[str, Any]:
    """Prüft die Prüfsummenkette vom ersten bis zum letzten Eintrag."""
    audit.seal(db)
    return audit.verify(db)


@router.get("/export.csv")
def export_csv(db: DB, _: CurrentActor, q: str = "", kind: Kind = "") -> Response:
    audit.seal(db)
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["id", "zeit_utc", "wer", "aktion", "betrifft", "details", "ip", "hash"])
    for e in db.scalars(_filtered(db, q, kind).order_by(AuditEntry.id)):
        w.writerow(
            [
                e.id,
                e.created_at.isoformat(timespec="seconds"),
                e.actor,
                e.action,
                e.target,
                json.dumps(e.details or {}, ensure_ascii=False) if e.details else "",
                e.ip or "",
                e.hash or "",
            ]
        )
    # BOM, damit Excel Umlaute richtig liest
    return Response(
        "﻿" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="tesseract-audit.csv"'},
    )
