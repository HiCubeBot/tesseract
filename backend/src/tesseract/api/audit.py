from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import or_, select

from tesseract.db.models import AuditEntry
from tesseract.deps import DB, CurrentActor

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditOut(BaseModel):
    id: int
    created_at: datetime
    actor: str
    action: str
    target: str
    details: dict[str, Any]
    ip: str | None


@router.get("")
def list_audit(
    db: DB,
    _: CurrentActor,
    q: str = "",
    limit: int = Query(100, ge=1, le=500),
    before_id: int | None = None,
) -> list[AuditOut]:
    stmt = select(AuditEntry).order_by(AuditEntry.id.desc()).limit(limit)
    if before_id:
        stmt = stmt.where(AuditEntry.id < before_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                AuditEntry.actor.ilike(like),
                AuditEntry.action.ilike(like),
                AuditEntry.target.ilike(like),
            )
        )
    return [AuditOut.model_validate(e, from_attributes=True) for e in db.scalars(stmt)]
