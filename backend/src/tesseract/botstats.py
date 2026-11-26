"""Statistik zum Bot-Schutz (Anubis) – aus der eigenen Log-Datenbank.

Was sich aus dem Zugriffs-Log ablesen lässt:
- **zur Prüfung geschickt:** Grund „bot“, Status 307 (Weiterleitung zur Anubis-Seite)
- **abgewiesen:** Grund „bot“, anderer Status (meist 403 – bekannte schlechte Bots)
- **bestanden / gescheitert:** Aufrufe von `…/api/pass-challenge` mit 3xx bzw. 4xx
Dazu Besucher (IPs), die geprüft wurden und nie bestanden haben – meist Bots ohne JavaScript.
"""

from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tesseract.caddy.config import ANUBIS_PASS
from tesseract.clients import classify
from tesseract.db.models import Host, LogEntry, Node, utcnow

RANGES = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
HOUR = func.strftime("%Y-%m-%dT%H:00:00Z", LogEntry.ts)
KEYS = ("challenged", "denied", "passed", "failed")


def _where(stmt, since, until, node: str | None):
    stmt = stmt.where(LogEntry.ts >= since, LogEntry.ts < until)
    if node:
        stmt = stmt.where(LogEntry.node_id.in_(select(Node.id).where(Node.name == node)))
    return stmt


def _bot(stmt):
    return stmt.where(LogEntry.reason == "bot")


def _pass(stmt):
    return stmt.where(LogEntry.uri.like(ANUBIS_PASS + "%"))


def _kind_of_bot(status: int) -> str:
    return "challenged" if status == 307 else "denied"


def _kind_of_pass(status: int) -> str | None:
    if 300 <= status < 400:
        return "passed"
    if status >= 400:
        return "failed"
    return None


def _totals(db: Session, since, until, node) -> dict[str, int]:
    out = dict.fromkeys(KEYS, 0)
    q = _where(select(LogEntry.status, func.count()), since, until, node)
    for status, n in db.execute(_bot(q).group_by(LogEntry.status)):
        out[_kind_of_bot(status)] += n
    for status, n in db.execute(_pass(q).group_by(LogEntry.status)):
        k = _kind_of_pass(status)
        if k:
            out[k] += n
    return out


def bots(db: Session, range_: str, node: str | None = None) -> dict[str, Any]:
    span = RANGES.get(range_, RANGES["24h"])
    now = utcnow()
    since = now - span
    totals = _totals(db, since, now, node)
    previous = _totals(db, since - span, since, node)

    # Verlauf je Stunde
    hourly: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(KEYS, 0))
    q = _where(select(HOUR, LogEntry.status, func.count()), since, now, node)
    for h, status, n in db.execute(_bot(q).group_by(HOUR, LogEntry.status)):
        hourly[h][_kind_of_bot(status)] += n
    for h, status, n in db.execute(_pass(q).group_by(HOUR, LogEntry.status)):
        k = _kind_of_pass(status)
        if k:
            hourly[h][k] += n

    # je Host
    hosts: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(KEYS, 0))
    q = _where(select(LogEntry.host, LogEntry.status, func.count()), since, now, node)
    for host, status, n in db.execute(_bot(q).group_by(LogEntry.host, LogEntry.status)):
        hosts[host][_kind_of_bot(status)] += n
    for host, status, n in db.execute(_pass(q).group_by(LogEntry.host, LogEntry.status)):
        k = _kind_of_pass(status)
        if k:
            hosts[host][k] += n
    by_host = sorted(
        ({"host": h, **v} for h, v in hosts.items()),
        key=lambda r: -(r["challenged"] + r["denied"]),
    )

    # Besucher: geprüft, bestanden, nie bestanden
    challenged_ips = {
        ip
        for (ip,) in db.execute(
            _bot(_where(select(LogEntry.ip), since, now, node))
            .where(LogEntry.status == 307)
            .distinct()
        )
    }
    passed_ips = {
        ip
        for (ip,) in db.execute(
            _pass(_where(select(LogEntry.ip), since, now, node))
            .where(LogEntry.status.between(300, 399))
            .distinct()
        )
    }
    denied_ips = {
        ip
        for (ip,) in db.execute(
            _bot(_where(select(LogEntry.ip), since, now, node))
            .where(LogEntry.status != 307)
            .distinct()
        )
    }

    # Wer abgefangen wurde: User-Agents (mit Erkennung), Länder, IPs
    agents: dict[str, dict[str, Any]] = {}
    q = _where(select(LogEntry.user_agent, LogEntry.status, func.count()), since, now, node)
    for ua, status, n in db.execute(_bot(q).group_by(LogEntry.user_agent, LogEntry.status)):
        key = (ua or "")[:255]
        row = agents.setdefault(key, {"user_agent": key, "challenged": 0, "denied": 0})
        row[_kind_of_bot(status)] += n
    top_agents = []
    for row in sorted(agents.values(), key=lambda r: -(r["challenged"] + r["denied"]))[:15]:
        kind, name = classify(row["user_agent"])
        top_agents.append({**row, "kind": kind, "name": name})

    countries = [
        {"country": c, "count": n}
        for c, n in db.execute(
            _bot(_where(select(LogEntry.country, func.count()), since, now, node))
            .where(LogEntry.country.is_not(None))
            .group_by(LogEntry.country)
            .order_by(func.count().desc())
            .limit(15)
        )
    ]
    top_ips = []
    for ip, country, n in db.execute(
        _bot(
            _where(select(LogEntry.ip, func.max(LogEntry.country), func.count()), since, now, node)
        )
        .group_by(LogEntry.ip)  # je IP einmal, auch wenn sich das Land geändert hat
        .order_by(func.count().desc())
        .limit(15)
    ):
        top_ips.append(
            {
                "ip": ip,
                "country": country,
                "count": n,
                "passed": ip in passed_ips,
                "denied": ip in denied_ips,
            }
        )

    protected = [
        h.domain for h in db.query(Host).filter(Host.bot_protection.is_(True)).order_by(Host.domain)
    ]
    rate = round(100 * totals["passed"] / totals["challenged"], 1) if totals["challenged"] else None
    return {
        "since": since,
        "totals": totals,
        "previous": previous,
        "pass_rate": rate,
        "visitors": {
            "challenged": len(challenged_ips),
            "passed": len(passed_ips),
            "never_passed": len(challenged_ips - passed_ips),
            "denied": len(denied_ips),
        },
        "hourly": [{"t": h, **v} for h, v in sorted(hourly.items())],
        "by_host": by_host,
        "agents": top_agents,
        "countries": countries,
        "top_ips": top_ips,
        "protected_hosts": protected,
    }
