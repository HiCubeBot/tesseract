"""Uptime-Monitor, Statistik › Betrieb und die öffentliche Statusseite."""

from collections import defaultdict
from datetime import timedelta
from statistics import median
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi import status as http
from sqlalchemy import func, select

from tesseract import monitor
from tesseract.db.models import Host, Incident, Node, StatsDaily, utcnow
from tesseract.deps import DB, AppSettings, CurrentActor
from tesseract.services import get_general
from tesseract.statsview import records

router = APIRouter(tags=["monitor"])
public = APIRouter(tags=["status"])


def _state(st) -> dict[str, Any]:
    if st is None:
        return {"status": "unknown", "since": None, "checked_at": None, "ms": None, "error": None}
    return {
        "status": st.status,
        "since": st.since,
        "checked_at": st.checked_at,
        "ms": st.ms,
        "error": st.error,
    }


@router.get("/monitor")
def overview(db: DB, _: CurrentActor, days: int = 30) -> dict[str, Any]:
    """Nodes und überwachte Hosts: aktueller Stand, Erreichbarkeit je Tag, letzte Vorfälle."""
    days = max(1, min(days, 90))
    nodes = [n for n in db.scalars(select(Node).order_by(Node.name)) if n.joined]
    hosts = list(
        db.scalars(
            select(Host)
            .where(Host.draft.is_(False), Host.enabled.is_(True), Host.monitor.is_(True))
            .order_by(Host.domain)
        )
    )
    states = monitor.states(db)
    av_nodes = monitor.availability(db, "node", [n.name for n in nodes], days)
    av_hosts = monitor.availability(db, "host", [h.domain for h in hosts], days)
    incidents = db.scalars(select(Incident).order_by(Incident.started_at.desc()).limit(20)).all()
    host_rows = [
        {
            "id": h.id,
            "domain": h.domain,
            "node": h.node.name,
            "public": h.status_public,
            "name": h.status_name,
            **_state(states.get(("host", h.domain))),
            **av_hosts[h.domain],
        }
        for h in hosts
    ]
    # Probleme zuerst: aktuell nicht erreichbar, dann geringste Erreichbarkeit
    host_rows.sort(key=lambda x: (x["status"] != "down", x["pct"] if x["pct"] is not None else 101))
    return {
        "days": monitor.days_back(days),
        "nodes": [
            {
                "name": n.name,
                "location": n.location,
                **_state(states.get(("node", n.name))),
                **av_nodes[n.name],
            }
            for n in nodes
        ],
        "hosts": host_rows,
        "incidents": [
            {
                "kind": i.kind,
                "ref": i.ref,
                "started_at": i.started_at,
                "ended_at": i.ended_at,
                "minutes": round(((i.ended_at or utcnow()) - i.started_at).total_seconds() / 60),
                "error": i.error,
            }
            for i in incidents
        ],
    }


@router.get("/stats/operations")
def operations(db: DB, _: CurrentActor, settings: AppSettings) -> dict[str, Any]:
    """Statistik › Betrieb: Summen seit Beginn, Rekorde, schnellster/langsamster Host."""
    tot = db.execute(
        select(
            func.coalesce(func.sum(StatsDaily.requests), 0),
            func.coalesce(func.sum(StatsDaily.bytes_out), 0),
            func.coalesce(func.sum(StatsDaily.denied), 0),
            func.min(StatsDaily.day),
            func.count(func.distinct(StatsDaily.day)),
        )
    ).one()
    since = (utcnow() - timedelta(days=30)).date().isoformat()
    medians: dict[str, list[float]] = defaultdict(list)
    for host, m in db.execute(
        select(StatsDaily.host, StatsDaily.median_ms).where(
            StatsDaily.day >= since,
            StatsDaily.median_ms.is_not(None),
            StatsDaily.requests >= 20,
        )
    ):
        if host and host != "-":
            medians[host].append(m)
    ranked = sorted((round(median(v), 1), h) for h, v in medians.items())
    rec = records(db)
    if ranked:
        rec["fastest"] = {"host": ranked[0][1], "median_ms": ranked[0][0]}
        rec["slowest"] = {"host": ranked[-1][1], "median_ms": ranked[-1][0]}
    days = int(tot[4] or 0)
    domain = settings.controller_domain
    return {
        "requests": int(tot[0]),
        "bytes_out": int(tot[1]),
        "denied": int(tot[2]),
        "first_day": tot[3],
        "days": days,
        "per_day_requests": round(int(tot[0]) / days) if days else 0,
        "per_day_bytes": round(int(tot[1]) / days) if days else 0,
        "records": rec,
        "status_url": f"https://{domain}/status" if domain else "/status",
        "status_enabled": bool(get_general(db)["status_page_enabled"]),
        "status_hosts": db.scalar(
            select(func.count()).select_from(Host).where(Host.status_public.is_(True))
        )
        or 0,
    }


@public.get("/status")
def status_page(db: DB) -> dict[str, Any]:
    """Öffentliche Statusseite: nur Hosts mit „Auf der Statusseite zeigen“, nur Name und Stand.
    Nur, wenn sie in den Einstellungen eingeschaltet ist – sonst 404."""
    if not get_general(db)["status_page_enabled"]:
        raise HTTPException(http.HTTP_404_NOT_FOUND, "Statusseite ist nicht eingeschaltet")
    hosts = list(
        db.scalars(
            select(Host)
            .where(Host.status_public.is_(True), Host.draft.is_(False))
            .order_by(Host.status_name, Host.domain)
        )
    )
    states = monitor.states(db)
    av = monitor.availability(db, "host", [h.domain for h in hosts], 90)
    services = []
    for h in hosts:
        st = states.get(("host", h.domain))
        paused = not h.enabled or not h.monitor
        status = "paused" if paused else (st.status if st else "unknown")
        a = av[h.domain]
        services.append(
            {
                "name": h.status_name or h.domain,
                "status": status,
                "since": st.since if st and not paused else None,
                "pct": a["pct"],
                "days": [
                    {"day": d["day"], "pct": d["pct"], "down_minutes": d["down_minutes"]}
                    for d in a["days"]
                ],
            }
        )
    down = sum(1 for s in services if s["status"] == "down")
    checked = sum(1 for s in services if s["status"] in ("up", "down"))
    if not services:
        overall = "none"
    elif not checked:
        overall = "pending"
    elif down == len(services):
        overall = "down"
    else:
        overall = "partial" if down else "ok"
    return {"checked_at": utcnow(), "overall": overall, "services": services}
