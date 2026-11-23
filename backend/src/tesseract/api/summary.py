"""Kurzübersicht für die Seitenleiste: Anzahl Hosts, Personen, Geräte, Nodes."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from tesseract.db.models import Device, Host, Node, Person
from tesseract.deps import DB, CurrentActor

router = APIRouter(tags=["system"])


class Counts(BaseModel):
    hosts: int
    persons: int
    devices: int
    nodes: int


@router.get("/counts")
def counts(db: DB, _: CurrentActor) -> Counts:
    def n(stmt) -> int:
        return int(db.scalar(stmt) or 0)

    return Counts(
        # Entwürfe zählen nicht – sie sind noch nicht ausgerollt
        hosts=n(select(func.count()).select_from(Host).where(Host.draft.is_(False))),
        persons=n(select(func.count()).select_from(Person)),
        # nur gültige Geräte (nicht gesperrt)
        devices=n(select(func.count()).select_from(Device).where(Device.revoked_at.is_(None))),
        # beigetretene Nodes (offene Einladungen nicht)
        nodes=sum(1 for node in db.scalars(select(Node)) if node.joined),
    )
