"""Zentrale Logs (Phase 5): Suche, Live-Ansicht, Details, Aktionen."""

from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select

from tesseract import audit
from tesseract import nodes as node_svc
from tesseract.db.models import Device, Host, LogEntry, Node, utcnow
from tesseract.deps import DB, AppSettings, CurrentActor
from tesseract.logs import CRS_SCORE_RULES, FILTERS, QueryError, apply_filter, apply_query
from tesseract.services import add_version, apply_node, diff, snapshot

router = APIRouter(prefix="/logs", tags=["logs"])


class LogOut(BaseModel):
    id: int
    ts: datetime
    node: str
    host: str
    method: str
    uri: str
    status: int
    duration_ms: float
    size: int
    ip: str
    country: str | None
    device: str | None
    person: str | None
    reason: str
    waf_rules: list[int]
    waf_msg: str | None
    waf_score: int | None
    user_agent: str | None


class Source(BaseModel):
    node: str
    kind: str
    state: str
    last_entry_at: datetime | None


class LogPage(BaseModel):
    entries: list[LogOut]
    sources: list[Source]
    geoip: bool


class LogDetail(LogOut):
    host_id: int | None
    waf_mode: str | None
    waf_exclusions: list[int]
    # Diese IP in den letzten 24 Stunden
    ip_requests: int
    ip_denied: int
    ip_banned: bool


def _out(e: LogEntry, nodes: dict[int, str], devices: dict[int, Device]) -> LogOut:
    d = devices.get(e.device_id) if e.device_id else None
    return LogOut(
        id=e.id,
        ts=e.ts,
        node=nodes.get(e.node_id, "?"),
        host=e.host,
        method=e.method,
        uri=e.uri,
        status=e.status,
        duration_ms=e.duration_ms,
        size=e.size,
        ip=e.ip,
        country=e.country,
        device=d.name if d else None,
        person=d.person.name if d else None,
        reason=e.reason,
        waf_rules=list(e.waf_rules or []),
        waf_msg=e.waf_msg,
        waf_score=e.waf_score,
        user_agent=e.user_agent,
    )


def _lookups(db, entries: list[LogEntry]) -> tuple[dict[int, str], dict[int, Device]]:
    nodes = dict(db.execute(select(Node.id, Node.name)).all())
    ids = {e.device_id for e in entries if e.device_id}
    devices = {d.id: d for d in db.scalars(select(Device).where(Device.id.in_(ids)))} if ids else {}
    return nodes, devices


@router.get("")
def list_logs(
    request: Request,
    db: DB,
    _: CurrentActor,
    q: str = "",
    filter: str = "all",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    before_id: int | None = None,
    after_id: int | None = None,
) -> LogPage:
    """Neueste zuerst. `before_id` blättert zurück, `after_id` holt nur Neues (Live)."""
    if filter not in FILTERS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unbekannter Filter")
    stmt = select(LogEntry)
    try:
        stmt = apply_query(stmt, q)
    except QueryError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    stmt = apply_filter(stmt, filter)
    if before_id:
        stmt = stmt.where(LogEntry.id < before_id)
    if after_id:
        stmt = stmt.where(LogEntry.id > after_id)
    entries = list(db.scalars(stmt.order_by(LogEntry.id.desc()).limit(limit)))
    nodes, devices = _lookups(db, entries)
    last = dict(
        db.execute(select(LogEntry.node_id, func.max(LogEntry.ts)).group_by(LogEntry.node_id)).all()
    )
    now = utcnow()
    sources = [
        Source(
            node=n.name,
            kind=n.kind,
            state=node_svc.state(n, now),
            last_entry_at=last.get(n.id),
        )
        for n in db.scalars(select(Node).order_by(Node.name))
        if n.joined
    ]
    return LogPage(
        entries=[_out(e, nodes, devices) for e in entries],
        sources=sources,
        geoip=request.app.state.logs.geo.ready,
    )


def _entry(db, entry_id: int) -> LogEntry:
    e = db.get(LogEntry, entry_id)
    if e is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Eintrag nicht gefunden (evtl. schon gelöscht)"
        )
    return e


def _host_for(db, name: str) -> Host | None:
    host = db.scalar(select(Host).where(Host.domain == name))
    if host is None and "." in name:
        host = db.scalar(select(Host).where(Host.domain == "*." + name.split(".", 1)[1]))
    return host


@router.get("/{entry_id}")
def get_entry(entry_id: int, db: DB, _: CurrentActor) -> LogDetail:
    e = _entry(db, entry_id)
    nodes, devices = _lookups(db, [e])
    host = _host_for(db, e.host)
    since = utcnow() - timedelta(hours=24)
    base = (
        select(func.count()).select_from(LogEntry).where(LogEntry.ip == e.ip, LogEntry.ts >= since)
    )
    denied = base.where((LogEntry.reason != "ok") | (LogEntry.status >= 400))
    from tesseract.services import active_bans

    return LogDetail(
        **_out(e, nodes, devices).model_dump(),
        host_id=host.id if host else None,
        waf_mode=host.waf_mode if host else None,
        waf_exclusions=list(host.waf_exclusions or []) if host else [],
        ip_requests=db.scalar(base) or 0,
        ip_denied=db.scalar(denied) or 0,
        ip_banned=e.ip in active_bans(db),
    )


@router.post("/{entry_id}/exclude")
def exclude_rules(
    entry_id: int, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> dict[str, Any]:
    """Fehlalarm: die Regeln dieses Eintrags beim Host als Ausnahme eintragen und übertragen."""
    e = _entry(db, entry_id)
    rules = [r for r in (e.waf_rules or []) if r not in CRS_SCORE_RULES]
    if not rules:
        raise HTTPException(status.HTTP_409_CONFLICT, "Der Eintrag hat keine WAF-Regel")
    host = _host_for(db, e.host)
    if host is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Kein Host für {e.host}")
    new = [r for r in rules if r not in (host.waf_exclusions or [])]
    if not new:
        return {"ok": True, "added": [], "host": host.domain, "error": None}
    before = snapshot(host)
    host.waf_exclusions = sorted({*(host.waf_exclusions or []), *new})
    db.flush()
    host.version += 1
    add_version(db, host, actor=actor.name, comment=f"Ausnahme aus Log #{e.id}")
    audit.record(
        db,
        actor=actor.name,
        action="host_updated",
        target=host.domain,
        details={"version": host.version, "changes": diff(before, snapshot(host))},
        ip=actor.ip,
    )
    db.commit()
    err = apply_node(db, host.node, settings, request.app.state.caddy_transport)
    db.commit()
    return {"ok": err is None, "added": new, "host": host.domain, "error": err}
