"""Uptime-Monitor: prüft jede Minute, ob Nodes verbunden und die Ziele der Hosts erreichbar sind.

- Node: verbunden, solange der Agent sich meldet (lokaler Node: Caddy erreichbar).
- Host: Ziel (upstream) per TCP vom Node aus – beim lokalen Node prüft der Controller selbst,
  bei Agent-Nodes der Agent (Aufgabe „tcp“). Ist der Node getrennt, gilt der Host als nicht
  erreichbar („Node getrennt“).
- Als Ausfall zählt erst der zweite Fehlschlag in Folge (kein Alarm bei einem Aussetzer).
  Beginn und Ende eines Ausfalls landen im Audit-Log (→ Benachrichtigungen) und als Vorfall.
- Je Tag: Anzahl Prüfungen, davon erreichbar, Ausfallzeit – für Statistik › Betrieb und die
  öffentliche Statusseite.
"""

import asyncio
import logging
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract import audit
from tesseract import nodes as node_svc
from tesseract.agent_tasks import supports_tasks
from tesseract.db.models import Host, Incident, MonitorState, Node, UptimeDaily, utcnow

log = logging.getLogger("tesseract.monitor")

INTERVAL = 60.0
# so viele Fehlschläge in Folge, bis ein Ausfall zählt
CONFIRM = 2
PARALLEL = 16


@dataclass
class Result:
    kind: str
    ref: str
    ok: bool | None  # None = nicht prüfbar (z. B. alter Agent)
    ms: float | None = None
    error: str | None = None


def tcp_check(host: str, port: int, timeout: float = 3.0) -> tuple[bool, float | None, str | None]:
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as e:
        return False, None, (e.strerror or str(e) or type(e).__name__)[:200]
    return True, round((time.perf_counter() - start) * 1000, 1), None


def _node_up(node: Node, now: datetime) -> tuple[bool, str | None]:
    st = node_svc.state(node, now)
    if st == "offline":
        return False, "keine Verbindung zum Controller"
    if not node.is_agent and st == "error":
        return False, (node.last_apply_error or "Caddy nicht erreichbar")[:200]
    return True, None


async def check_all(app, now: datetime | None = None) -> list[Result]:
    """Eine Runde: alle Nodes und überwachten Hosts prüfen (ohne zu speichern)."""
    now = now or utcnow()
    broker = getattr(app.state, "agent_tasks", None)
    with app.state.db.sessionmaker() as db:
        nodes = [n for n in db.scalars(select(Node)) if n.joined]
        hosts = list(
            db.scalars(
                select(Host).where(
                    Host.enabled.is_(True), Host.draft.is_(False), Host.monitor.is_(True)
                )
            )
        )
        node_info = {n.id: (n, *_node_up(n, now)) for n in nodes}
        targets = [
            (h.domain, h.node_id, h.upstream_host, h.upstream_port)
            for h in hosts
            if h.node_id in node_info
        ]
        tasks_ok = {n.id: supports_tasks(n) for n in nodes}
        local = {n.id for n in nodes if not n.is_agent}

    results = [Result("node", n.name, up, error=err) for n, up, err in node_info.values()]
    sem = asyncio.Semaphore(PARALLEL)

    async def one(domain: str, node_id: int, host: str, port: int) -> Result:
        _node, up, _err = node_info[node_id]
        if not up:
            return Result("host", domain, False, error="Node getrennt")
        async with sem:
            if node_id in local:
                ok, ms, err = await asyncio.to_thread(tcp_check, host, port)
                return Result("host", domain, ok, ms, err)
            if broker is None or not tasks_ok.get(node_id):
                return Result("host", domain, None, error="Agent zu alt für Prüfungen")
            r = await broker.run(node_id, "tcp", {"host": host, "port": port}, timeout=10.0)
            if r is None:
                return Result("host", domain, None, error="Agent antwortet nicht")
            return Result("host", domain, bool(r.get("ok")), r.get("ms"), r.get("error"))

    results += await asyncio.gather(*(one(*t) for t in targets))
    return results


def record(
    db: Session,
    results: list[Result],
    now: datetime | None = None,
    interval: float = INTERVAL,
    fails: dict[tuple[str, str], int] | None = None,
) -> list[tuple[str, str, str]]:
    """Ergebnisse speichern. Rückgabe: Wechsel [(Art, Name, "down"|"up")]."""
    now = now or utcnow()
    day = now.date().isoformat()
    fails = fails if fails is not None else {}
    changes = []
    for r in results:
        if r.ok is None:
            continue
        key = (r.kind, r.ref)
        st = db.get(MonitorState, key)
        if st is None:
            st = MonitorState(kind=r.kind, ref=r.ref, status="unknown", since=now)
            db.add(st)
        fails[key] = 0 if r.ok else fails.get(key, 0) + 1
        # erst nach CONFIRM Fehlschlägen als Ausfall werten
        new = "up" if r.ok else ("down" if fails[key] >= CONFIRM else st.status)
        if new == "unknown":
            new = "up" if r.ok else "unknown"
        st.checked_at = now
        st.ms = r.ms
        st.error = None if r.ok else r.error
        daily = db.get(UptimeDaily, (day, r.kind, r.ref))
        if daily is None:
            daily = UptimeDaily(day=day, kind=r.kind, ref=r.ref, checks=0, up=0, down_seconds=0)
            daily.outages = 0
            db.add(daily)
        daily.checks += 1
        if r.ok:
            daily.up += 1
        elif new == "down":
            daily.down_seconds += int(interval * (CONFIRM if st.status != "down" else 1))
        if new != st.status:
            if new == "down":
                daily.outages += 1
                db.add(Incident(kind=r.kind, ref=r.ref, started_at=now, error=r.error))
                changes.append((r.kind, r.ref, "down"))
            elif st.status == "down":
                inc = db.scalar(
                    select(Incident)
                    .where(Incident.kind == r.kind, Incident.ref == r.ref)
                    .where(Incident.ended_at.is_(None))
                    .order_by(Incident.started_at.desc())
                )
                if inc is not None:
                    inc.ended_at = now
                changes.append((r.kind, r.ref, "up"))
            st.status = new
            st.since = now
    # Hosts melden (Nodes meldet bereits nodes.watch_local bzw. der Agent-Status)
    for kind, ref, what in changes:
        if kind != "host":
            continue
        err = next((r.error for r in results if r.kind == kind and r.ref == ref), None)
        audit.record(
            db,
            actor="Monitor",
            action="host_down" if what == "down" else "host_up",
            target=ref,
            details={"error": err} if what == "down" and err else {},
        )
    return changes


async def watch(app, interval: float = INTERVAL) -> None:
    fails: dict[tuple[str, str], int] = {}
    while True:
        try:
            results = await check_all(app)
            with app.state.db.sessionmaker() as db:
                for kind, ref, what in record(db, results, interval=interval, fails=fails):
                    log.warning(
                        "%s %s %s", kind, ref, "ausgefallen" if what == "down" else "wieder da"
                    )
                db.commit()
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover – die Schleife darf nie sterben
            log.exception("Monitor: Fehler bei der Prüfung")
        await asyncio.sleep(interval)


# ---------- Auswertung ----------


def days_back(n: int, now: datetime | None = None) -> list[str]:
    today = (now or utcnow()).date()
    return [(today - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def availability(db: Session, kind: str, refs: list[str], days: int = 30) -> dict[str, Any]:
    """Je Name: Tage [{day, checks, up, down_seconds}] und Anteil erreichbar über alle Tage."""
    span = days_back(days)
    rows = db.scalars(
        select(UptimeDaily).where(UptimeDaily.kind == kind, UptimeDaily.day >= span[0])
    ).all()
    by: dict[str, dict[str, UptimeDaily]] = {}
    for r in rows:
        by.setdefault(r.ref, {})[r.day] = r
    out = {}
    for ref in refs:
        d = by.get(ref, {})
        checks = sum(x.checks for x in d.values())
        up = sum(x.up for x in d.values())
        out[ref] = {
            "days": [
                {
                    "day": day,
                    "checks": d[day].checks if day in d else 0,
                    "down_minutes": round(d[day].down_seconds / 60) if day in d else 0,
                    "outages": d[day].outages if day in d else 0,
                    "pct": round(100 * d[day].up / d[day].checks, 2)
                    if day in d and d[day].checks
                    else None,
                }
                for day in span
            ],
            "pct": round(100 * up / checks, 2) if checks else None,
            "outages": sum(x.outages for x in d.values()),
            "down_minutes": round(sum(x.down_seconds for x in d.values()) / 60),
        }
    return out


def states(db: Session) -> dict[tuple[str, str], MonitorState]:
    return {(s.kind, s.ref): s for s in db.scalars(select(MonitorState))}
