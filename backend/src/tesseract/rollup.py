"""Tages- und Stundenwerte aus den Logs verdichten (für „Gesamter Zeitraum“ und Rekorde).

Läuft vor dem Löschen alter Logs (`Collector.prune`): Jeder abgeschlossene Tag (UTC), der
noch nicht verdichtet ist, wird einmal zusammengefasst. Danach dürfen seine Einzeleinträge
verschwinden – die Tageswerte bleiben.
"""

import logging
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from statistics import median
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from tesseract.clients import classify
from tesseract.db.models import (
    LogEntry,
    Node,
    Setting,
    StatsDaily,
    StatsHourly,
    VisitorIp,
    utcnow,
)
from tesseract.sqlstore import BOT_RE

log = logging.getLogger("tesseract.rollup")

STATE_KEY = "stats_rollup"
# höchstens so viele Tage pro Durchlauf (Nachholen nach einem Update)
MAX_DAYS = 31
MEDIAN_SAMPLE = 20_000


def _state(db: Session) -> str | None:
    row = db.get(Setting, STATE_KEY)
    return (row.value or {}).get("until") if row else None


def _set_state(db: Session, day: str) -> None:
    row = db.get(Setting, STATE_KEY)
    if row is None:
        db.add(Setting(key=STATE_KEY, value={"until": day}))
    else:
        row.value = {"until": day}


def day_values(db: Session, day: date) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set]:
    """Werte eines Tages aus den Logs: (je Host/Node, je Stunde, Besucher-IPs).

    Wird auch für den laufenden Tag genutzt (dann ohne zu speichern)."""
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    end = start + timedelta(days=1)
    names = dict(db.execute(select(Node.id, Node.name)).all())
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    visitors: dict[tuple[str, str], set[str]] = defaultdict(set)
    all_visitors: set[str] = set()
    durations: dict[tuple[str, str], list[float]] = defaultdict(list)
    hourly: dict[datetime, dict[str, Any]] = {}
    hour_hosts: dict[datetime, Counter[str]] = defaultdict(Counter)
    hour_denied_hosts: dict[datetime, Counter[str]] = defaultdict(Counter)

    def row(host: str, node: str) -> dict[str, Any]:
        key = (host, node)
        if key not in rows:
            rows[key] = {
                "day": day.isoformat(),
                "host": host,
                "node": node,
                **dict.fromkeys(
                    [
                        "requests",
                        "denied",
                        "mtls",
                        "waf",
                        "ipfilter",
                        "s2xx",
                        "s3xx",
                        "s4xx",
                        "s5xx",
                        "bytes_out",
                        "bytes_in",
                        "http1",
                        "http2",
                        "http3",
                        "browser",
                        "app",
                        "bot",
                        "compressed",
                        "compressible",
                        "visitors",
                    ],
                    0,
                ),
                "median_ms": None,
                "codes": Counter(),
                "clients": Counter(),
            }
        return rows[key]

    stmt = select(
        LogEntry.host,
        LogEntry.node_id,
        LogEntry.ts,
        LogEntry.reason,
        LogEntry.status,
        LogEntry.size,
        LogEntry.bytes_in,
        LogEntry.proto,
        LogEntry.encoding,
        LogEntry.user_agent,
        LogEntry.ip,
        LogEntry.duration_ms,
    ).where(LogEntry.ts >= start, LogEntry.ts < end, LogEntry.reason != "test")
    for host, node_id, ts, reason, status, size, b_in, proto, enc, ua, ip, dur in db.execute(
        stmt
    ).yield_per(5000):
        node = names.get(node_id, "?")
        r = row(host or "", node)
        r["requests"] += 1
        r["bytes_out"] += size or 0
        r["bytes_in"] += b_in or 0
        denied = reason != "ok"
        if denied:
            r["denied"] += 1
            if reason == "mtls":
                r["mtls"] += 1
            elif reason == "waf":
                r["waf"] += 1
            elif reason in ("ip", "ban", "internal"):
                r["ipfilter"] += 1
        cls = (status or 0) // 100
        if cls in (2, 3, 4, 5):
            r[f"s{cls}xx"] += 1
        if status:
            r["codes"][str(status)] += 1
        if proto == "3":
            r["http3"] += 1
        elif proto == "2":
            r["http2"] += 1
        elif proto:
            r["http1"] += 1
        kind, name = classify(ua)
        r[kind] += 1
        r["clients"][f"{kind}:{name}"] += 1
        if not denied and status == 200:
            r["compressible"] += 1
            if enc and enc != "identity":
                r["compressed"] += 1
        if not denied:
            if len(durations[(host or "", node)]) < MEDIAN_SAMPLE:
                durations[(host or "", node)].append(dur or 0.0)
            if ip and not BOT_RE.search(ua or ""):
                visitors[(host or "", node)].add(ip)
                all_visitors.add(ip)
        h = ts.replace(minute=0, second=0, microsecond=0)
        hr = hourly.setdefault(h, {"hour": h, "requests": 0, "denied": 0, "bytes_out": 0})
        hr["requests"] += 1
        hr["bytes_out"] += size or 0
        hour_hosts[h][host or ""] += 1
        if denied:
            hr["denied"] += 1
            hour_denied_hosts[h][host or ""] += 1

    for key, r in rows.items():
        r["visitors"] = len(visitors.get(key, ()))
        d = durations.get(key)
        r["median_ms"] = round(median(d), 2) if d else None
        r["codes"] = dict(r["codes"])
        r["clients"] = dict(r["clients"])
    for h, hr in hourly.items():
        hr["top_host"] = hour_hosts[h].most_common(1)[0][0] if hour_hosts[h] else None
        top_den = hour_denied_hosts[h].most_common(1)
        hr["top_denied_host"] = top_den[0][0] if top_den else None
    return list(rows.values()), list(hourly.values()), all_visitors


def store_day(db: Session, day: date) -> int:
    """Einen Tag verdichten und speichern (ersetzt vorhandene Werte dieses Tages)."""
    rows, hours, ips = day_values(db, day)
    d = day.isoformat()
    db.execute(delete(StatsDaily).where(StatsDaily.day == d))
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    db.execute(
        delete(StatsHourly).where(
            StatsHourly.hour >= start, StatsHourly.hour < start + timedelta(days=1)
        )
    )
    for r in rows:
        db.add(StatsDaily(**r))
    for h in hours:
        db.add(StatsHourly(**h))
    if ips:
        known = {
            v.ip: v
            for chunk in _chunks(sorted(ips), 500)
            for v in db.scalars(select(VisitorIp).where(VisitorIp.ip.in_(chunk)))
        }
        for ip in ips:
            v = known.get(ip)
            if v is None:
                db.add(VisitorIp(ip=ip, first_day=d, last_day=d))
            else:
                v.first_day = min(v.first_day, d)
                v.last_day = max(v.last_day, d)
    return len(rows)


def _chunks(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i : i + n]


def run(db: Session, now: datetime | None = None) -> int:
    """Alle abgeschlossenen, noch nicht verdichteten Tage verdichten. Commit macht der Aufrufer."""
    now = now or utcnow()
    today = now.date()
    until = _state(db)
    if until:
        day = date.fromisoformat(until) + timedelta(days=1)
    else:
        first = db.scalar(select(func.min(LogEntry.ts)))
        if first is None:
            return 0
        day = first.date()
    done = 0
    while day < today and done < MAX_DAYS:
        store_day(db, day)
        _set_state(db, day.isoformat())
        db.flush()
        done += 1
        day += timedelta(days=1)
    if done:
        log.info("Statistik: %d Tag(e) verdichtet (bis %s)", done, day - timedelta(days=1))
    return done
