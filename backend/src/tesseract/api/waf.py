"""WAF-Regeln nachschlagen und Ausnahmen zentral verwalten (siehe wafrules.py)."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from tesseract import audit, wafrules
from tesseract.db.models import Host, WafException, utcnow
from tesseract.deps import DB, AppSettings, CurrentActor
from tesseract.services import add_version, apply_node, diff, snapshot

router = APIRouter(prefix="/waf", tags=["waf"])


# ---------- Regeln ----------


@router.get("/rules")
def list_rules(db: DB, _: CurrentActor) -> dict[str, Any]:
    """Katalog mit Treffern der letzten 24 h / 7 / 30 Tage und Zahl der Ausnahmen je Regel."""
    cat = wafrules.catalog()
    counts = wafrules.hits(db)
    excepted: dict[int, int] = {}
    for h in db.scalars(select(Host)):
        for r in h.waf_exclusions or []:
            excepted[r] = excepted.get(r, 0) + 1
        for a in h.areas:
            for r in a.waf_exclusions or []:
                excepted[r] = excepted.get(r, 0) + 1
    for e in db.scalars(select(WafException)):
        if e.target or e.path:
            excepted[e.rule_id] = excepted.get(e.rule_id, 0) + 1
    zero = dict.fromkeys(wafrules.WINDOWS, 0)
    rules = [
        {**r, "hits": counts.get(r["id"], zero), "exceptions": excepted.get(r["id"], 0)}
        for r in cat["rules"]
    ]
    # Treffer von Regeln, die der Katalog nicht kennt (andere CRS-Version), nicht verschlucken
    known = {r["id"] for r in rules}
    for rid, h in sorted(counts.items()):
        if rid not in known:
            rules.append(
                {
                    "id": rid,
                    "file": "",
                    "category": "Unbekannt",
                    "msg": "",
                    "paranoia": None,
                    "severity": None,
                    "phase": None,
                    "tags": [],
                    "hits": h,
                    "exceptions": excepted.get(rid, 0),
                }
            )
    return {"crs": cat["crs"], "coraza_caddy": cat["coraza_caddy"], "rules": rules}


@router.get("/rules/{rule_id}")
def get_rule(rule_id: int, db: DB, _: CurrentActor) -> dict[str, Any]:
    rule = wafrules.rules_by_id().get(rule_id)
    detail = wafrules.rule_detail(db, rule_id)
    if rule is None and not detail["hits"]["30d"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Regel nicht gefunden")
    return {
        "rule": rule or {"id": rule_id, "msg": "", "category": "Unbekannt", "tags": []},
        **detail,
        "exceptions": [x for x in _all_exceptions(db) if x["rule_id"] == rule_id],
    }


# ---------- Ausnahmen ----------


def _exc_out(e: WafException, host: Host, db) -> dict[str, Any]:
    targeted = bool(e.target or e.path)
    return {
        "id": e.id,
        "host_id": host.id,
        "host": host.domain,
        "area": None,
        "rule_id": e.rule_id,
        "target": e.target,
        "path": e.path,
        "comment": e.comment,
        "created_by": e.created_by,
        "created_at": e.created_at,
        "expires_at": e.expires_at,
        # bei ganzen Ausnahmen werden Treffer gar nicht mehr protokolliert
        "hits_since": wafrules.hits_since(db, host.domain, e.rule_id, e.created_at)
        if targeted
        else None,
    }


def _all_exceptions(db) -> list[dict[str, Any]]:
    """Alle Ausnahmen: Einträge mit Kommentar/Ablauf, dazu ganze Ausnahmen aus Hosts und
    Bereichen, die (noch) keinen Eintrag haben."""
    out: list[dict[str, Any]] = []
    rows = list(db.scalars(select(WafException).order_by(WafException.id)))
    meta = {(e.host_id, e.rule_id) for e in rows if not e.target and not e.path}
    hosts = {h.id: h for h in db.scalars(select(Host).order_by(Host.domain))}
    for e in rows:
        host = hosts.get(e.host_id)
        if host is None:
            continue
        # ganze Ausnahme, die am Host inzwischen entfernt wurde: nicht mehr anzeigen
        if not e.target and not e.path and e.rule_id not in (host.waf_exclusions or []):
            continue
        out.append(_exc_out(e, host, db))
    for host in hosts.values():
        for r in host.waf_exclusions or []:
            if (host.id, r) not in meta:
                out.append(_legacy(host, r))
        for a in host.areas:
            for r in a.waf_exclusions or []:
                out.append({**_legacy(host, r), "area": a.name or ", ".join(a.paths)})
    out.sort(key=lambda x: (x["host"], x["rule_id"], x["path"], x["target"]))
    return out


def _legacy(host: Host, rule: int) -> dict[str, Any]:
    return {
        "id": None,
        "host_id": host.id,
        "host": host.domain,
        "area": None,
        "rule_id": rule,
        "target": "",
        "path": "",
        "comment": "",
        "created_by": "",
        "created_at": None,
        "expires_at": None,
        "hits_since": None,
    }


@router.get("/exceptions")
def list_exceptions(db: DB, _: CurrentActor) -> list[dict[str, Any]]:
    return _all_exceptions(db)


class ExceptionIn(BaseModel):
    host_id: int
    rule_id: int = Field(ge=1, le=99_999_999)
    target: str = Field("", max_length=200)
    path: str = Field("", max_length=255)
    comment: str = Field("", max_length=255)
    expires_at: datetime | None = None

    @field_validator("target")
    @classmethod
    def _target(cls, v: str) -> str:
        return wafrules.clean_target(v)

    @field_validator("path")
    @classmethod
    def _path(cls, v: str) -> str:
        return wafrules.clean_path(v)


class ExceptionUpdate(BaseModel):
    comment: str = Field("", max_length=255)
    expires_at: datetime | None = None


def _utc(dt: datetime | None) -> datetime | None:
    """Zeitpunkt als UTC (ohne Angabe gilt UTC) – wie alle Zeiten in der Datenbank."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _host_changed(db, host: Host, before: dict, actor, comment: str) -> None:
    """Host geändert: neue Version und Audit-Eintrag (Commit macht der Aufrufer)."""
    db.flush()
    host.version += 1
    add_version(db, host, actor=actor.name, comment=comment)
    audit.record(
        db,
        actor=actor.name,
        action="host_updated",
        target=host.domain,
        details={"version": host.version, "changes": diff(before, snapshot(host))},
        ip=actor.ip,
    )


def _apply(request: Request, db, host: Host, settings) -> str | None:
    if host.draft or not host.enabled:
        return None
    return apply_node(db, host.node, settings, request.app.state.caddy_transport)


@router.post("/exceptions", status_code=status.HTTP_201_CREATED)
def create_exception(
    body: ExceptionIn, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> dict[str, Any]:
    host = db.get(Host, body.host_id)
    if host is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Host nicht gefunden")
    if wafrules.is_score_rule(body.rule_id):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Das ist eine Auswerte-Regel (Anomalie-Score) – die eigentliche Regel ausnehmen",
        )
    expires = _utc(body.expires_at)
    if expires is not None and expires <= utcnow():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Ablauf liegt in der Vergangenheit"
        )
    whole = not body.target and not body.path
    if whole:
        existing = db.scalar(
            select(WafException).where(
                WafException.host_id == host.id,
                WafException.rule_id == body.rule_id,
                WafException.target == "",
                WafException.path == "",
            )
        )
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Diese Ausnahme gibt es schon")
    e = WafException(
        host_id=host.id,
        rule_id=body.rule_id,
        target=body.target,
        path=body.path,
        comment=body.comment.strip(),
        created_by=actor.name,
        expires_at=expires,
    )
    db.add(e)
    changed_host = False
    if whole and body.rule_id not in (host.waf_exclusions or []):
        before = snapshot(host)
        host.waf_exclusions = sorted({*(host.waf_exclusions or []), body.rule_id})
        _host_changed(db, host, before, actor, f"WAF-Ausnahme {body.rule_id}")
        changed_host = True
    db.flush()
    audit.record(
        db,
        actor=actor.name,
        action="waf_exception_created",
        target=host.domain,
        details=wafrules.describe(e),
        ip=actor.ip,
    )
    db.commit()
    # ganze Ausnahme, die es am Host schon gab (nur Kommentar ergänzt): nichts zu übertragen
    err = _apply(request, db, host, settings) if (changed_host or not whole) else None
    db.commit()
    return {"exception": _exc_out(e, host, db), "error": err}


@router.put("/exceptions/{exc_id}")
def update_exception(
    exc_id: int, body: ExceptionUpdate, db: DB, actor: CurrentActor
) -> dict[str, Any]:
    e = db.get(WafException, exc_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ausnahme nicht gefunden")
    expires = _utc(body.expires_at)
    if expires is not None and expires <= utcnow():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Ablauf liegt in der Vergangenheit"
        )
    e.comment, e.expires_at = body.comment.strip(), expires
    audit.record(
        db,
        actor=actor.name,
        action="waf_exception_updated",
        target=e.host.domain,
        details=wafrules.describe(e),
        ip=actor.ip,
    )
    db.commit()
    return _exc_out(e, e.host, db)


def _remove_whole(db, host: Host, rule: int, actor) -> bool:
    if rule not in (host.waf_exclusions or []):
        return False
    before = snapshot(host)
    host.waf_exclusions = [r for r in host.waf_exclusions if r != rule]
    _host_changed(db, host, before, actor, f"WAF-Ausnahme {rule} entfernt")
    return True


@router.delete("/exceptions/{exc_id}")
def delete_exception(
    exc_id: int, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> dict[str, Any]:
    e = db.get(WafException, exc_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ausnahme nicht gefunden")
    host = e.host
    details = wafrules.describe(e)
    whole = not e.target and not e.path
    if whole:
        _remove_whole(db, host, e.rule_id, actor)
    db.delete(e)
    audit.record(
        db,
        actor=actor.name,
        action="waf_exception_deleted",
        target=host.domain,
        details=details,
        ip=actor.ip,
    )
    db.commit()
    err = _apply(request, db, host, settings)
    db.commit()
    return {"ok": err is None, "error": err}


@router.delete("/hosts/{host_id}/exclusions/{rule_id}")
def delete_host_exclusion(
    host_id: int,
    rule_id: int,
    request: Request,
    db: DB,
    actor: CurrentActor,
    settings: AppSettings,
) -> dict[str, Any]:
    """Ganze Ausnahme ohne Eintrag (direkt am Host gesetzt) entfernen."""
    host = db.get(Host, host_id)
    if host is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Host nicht gefunden")
    if not _remove_whole(db, host, rule_id, actor):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ausnahme nicht gefunden")
    db.commit()
    err = _apply(request, db, host, settings)
    db.commit()
    return {"ok": err is None, "error": err}
