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
from tesseract.logstore import Sel, StoreError, from_id, sel_from_query, store_for, to_id
from tesseract.services import add_version, apply_node, diff, get_general, snapshot

router = APIRouter(prefix="/logs", tags=["logs"])

_DENIED = ("waf", "ip", "ban", "mtls", "internal", "websocket", "authelia")


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
    # "local" (SQLite) oder "loki" / "victorialogs"
    store: str = "local"


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


# ---------- Externer Speicher (Loki / VictoriaLogs) ----------

# So weit schaut die Liste ohne Blättern zurück (Loki begrenzt Abfragen auf ~30 Tage)
LOOKBACK = timedelta(days=30)


def _store(request: Request, db):
    return store_for(get_general(db), getattr(request.app.state, "loki_transport", None))


def _ext_out(e: dict[str, Any]) -> LogOut:
    return LogOut(**{k: e[k] for k in LogOut.model_fields if k in e})


def _ext_entry(store, entry_id: int) -> dict[str, Any]:
    """Eintrag zu einer ID (Zeitstempel in µs) aus dem externen Speicher."""
    try:
        found = store.entries(
            Sel().add("reason", "ne", "test"),
            from_id(entry_id - 1000),
            from_id(entry_id + 1),
            20,
        )
    except StoreError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    for e in found:
        if e["id"] == entry_id or to_id(e["ts"]) == entry_id:
            return e
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Eintrag nicht gefunden (evtl. schon gelöscht)")


def _ext_list(store, q: str, filter: str, limit: int, before_id, after_id) -> list[LogOut]:
    try:
        sel = sel_from_query(q, filter).add("reason", "ne", "test")
    except QueryError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    end = from_id(before_id) if before_id else utcnow() + timedelta(minutes=1)
    start = from_id(after_id + 1) if after_id else end - LOOKBACK
    try:
        return [_ext_out(e) for e in store.entries(sel, start, end, limit)]
    except StoreError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e


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
    store = _store(request, db)
    if store is not None:
        entries_out = _ext_list(store, q, filter, limit, before_id, after_id)
        return LogPage(
            entries=entries_out,
            sources=_sources(db),
            geoip=request.app.state.logs.geo.ready,
            store=store.kind,
        )
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
    return LogPage(
        entries=[_out(e, nodes, devices) for e in entries],
        sources=_sources(db),
        geoip=request.app.state.logs.geo.ready,
    )


def _sources(db) -> list[Source]:
    last = dict(
        db.execute(select(LogEntry.node_id, func.max(LogEntry.ts)).group_by(LogEntry.node_id)).all()
    )
    now = utcnow()
    return [
        Source(
            node=n.name,
            kind=n.kind,
            state=node_svc.state(n, now),
            last_entry_at=last.get(n.id),
        )
        for n in db.scalars(select(Node).order_by(Node.name))
        if n.joined
    ]


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
def get_entry(entry_id: int, request: Request, db: DB, _: CurrentActor) -> LogDetail:
    from tesseract.services import active_bans

    store = _store(request, db)
    if store is not None:
        x = _ext_entry(store, entry_id)
        host = _host_for(db, x["host"])
        since = utcnow() - timedelta(hours=24)
        by_ip = Sel().add("reason", "ne", "test").add("ip", "eq", x["ip"])
        try:
            reqs = store.count(by_ip, since, utcnow())
            den = store.count(by_ip.copy().add("reason", "in", list(_DENIED)), since, utcnow())
        except StoreError as err:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(err)) from err
        return LogDetail(
            **_ext_out(x).model_dump(),
            host_id=host.id if host else None,
            waf_mode=host.waf_mode if host else None,
            waf_exclusions=list(host.waf_exclusions or []) if host else [],
            ip_requests=int(sum(v for *_, v in reqs)),
            ip_denied=int(sum(v for *_, v in den)),
            ip_banned=x["ip"] in active_bans(db),
        )
    e = _entry(db, entry_id)
    nodes, devices = _lookups(db, [e])
    host = _host_for(db, e.host)
    since = utcnow() - timedelta(hours=24)
    base = (
        select(func.count()).select_from(LogEntry).where(LogEntry.ip == e.ip, LogEntry.ts >= since)
    )
    denied = base.where((LogEntry.reason != "ok") | (LogEntry.status >= 400))

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
    store = _store(request, db)
    if store is not None:
        x = _ext_entry(store, entry_id)
        entry_rules, entry_host, ref = x["waf_rules"], x["host"], f"Log {x['ts']:%d.%m. %H:%M:%S}"
    else:
        e = _entry(db, entry_id)
        entry_rules, entry_host, ref = e.waf_rules or [], e.host, f"Log #{e.id}"
    rules = [r for r in entry_rules if r not in CRS_SCORE_RULES]
    if not rules:
        raise HTTPException(status.HTTP_409_CONFLICT, "Der Eintrag hat keine WAF-Regel")
    host = _host_for(db, entry_host)
    if host is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Kein Host für {entry_host}")
    new = [r for r in rules if r not in (host.waf_exclusions or [])]
    if not new:
        return {"ok": True, "added": [], "host": host.domain, "error": None}
    before = snapshot(host)
    host.waf_exclusions = sorted({*(host.waf_exclusions or []), *new})
    db.flush()
    host.version += 1
    add_version(db, host, actor=actor.name, comment=f"Ausnahme aus {ref}")
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
