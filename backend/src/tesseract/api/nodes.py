from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select

from tesseract import audit
from tesseract.caddy.config import redact
from tesseract.db.models import Host, Node
from tesseract.deps import DB, AppSettings, CurrentActor
from tesseract.services import apply_node, node_config, node_in_sync

router = APIRouter(prefix="/nodes", tags=["nodes"])


class NodeOut(BaseModel):
    id: int
    name: str
    location: str
    hosts: int
    last_applied_at: datetime | None
    last_apply_error: str | None
    in_sync: bool


def _get(db, node_id: int) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Node nicht gefunden")
    return node


@router.get("")
def list_nodes(db: DB, _: CurrentActor, settings: AppSettings) -> list[NodeOut]:
    counts = dict(db.execute(select(Host.node_id, func.count()).group_by(Host.node_id)).all())
    return [
        NodeOut(
            id=n.id,
            name=n.name,
            location=n.location,
            hosts=counts.get(n.id, 0),
            last_applied_at=n.last_applied_at,
            last_apply_error=n.last_apply_error,
            in_sync=node_in_sync(db, n, settings),
        )
        for n in db.scalars(select(Node).order_by(Node.name))
    ]


@router.get("/{node_id}/config")
def get_config(node_id: int, db: DB, _: CurrentActor, settings: AppSettings) -> dict[str, Any]:
    """Die Caddy-Config, die der Controller für diesen Node erzeugt (ohne Geheimnisse)."""
    return redact(node_config(db, _get(db, node_id), settings))


@router.post("/{node_id}/apply")
def apply(
    node_id: int, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> dict[str, Any]:
    node = _get(db, node_id)
    err = apply_node(db, node, settings, request.app.state.caddy_transport)
    audit.record(
        db,
        actor=actor.name,
        action="config_applied" if err is None else "config_apply_failed",
        target=node.name,
        details={"error": err} if err else {},
        ip=actor.ip,
    )
    db.commit()
    return {"ok": err is None, "error": err}
