"""Phase 5: Statistik aus den gesammelten Logs.

Zeitreihen kommen als Stunden-Buckets in UTC (`2026-11-18T10:00:00Z`); das Frontend fasst
sie in Ortszeit zusammen (6-Stunden-/Tages-Balken, Wochentag × Uhrzeit).
"""

from collections import Counter, defaultdict
from datetime import timedelta
from statistics import median
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from tesseract.caddy.config import ANUBIS_PASS
from tesseract.db.models import Device, LogEntry, Node, Person, utcnow

RANGES = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
DENIED_REASONS = ("waf", "ip", "ban", "mtls", "internal", "websocket", "authelia", "bot")
# Angriffsarten nach CRS-Regelbereich
ATTACK_FAMILIES = [
    (913, "Scanner"),
    (920, "Protokoll-Verstöße"),
    (921, "Protokoll-Angriffe"),
    (930, "Pfad-Traversal / LFI"),
    (931, "Remote File Inclusion"),
    (932, "Befehlsausführung (RCE)"),
    (933, "PHP-Injection"),
    (934, "Generische Angriffe"),
    (941, "Cross-Site-Scripting"),
    (942, "SQL-Injection"),
    (943, "Session-Fixation"),
    (944, "Java-Angriffe"),
]
PERCENTILE_SAMPLE = 50_000


def family(rule: int) -> str:
    block = rule // 1000
    for start, name in ATTACK_FAMILIES:
        if block == start:
            return name
    return "Sonstige"


HOUR = func.strftime("%Y-%m-%dT%H:00:00Z", LogEntry.ts)


def _hour() -> Any:
    return HOUR


def _base(range_: str, node: str | None) -> tuple[Select, Any]:
    since = utcnow() - RANGES.get(range_, RANGES["24h"])
    stmt = select().select_from(LogEntry).where(LogEntry.ts >= since)
    if node:
        stmt = stmt.where(LogEntry.node_id.in_(select(Node.id).where(Node.name == node)))
    return stmt, since


def _denied() -> Any:
    return LogEntry.reason.in_(DENIED_REASONS)


def _with(stmt: Select, *cols: Any) -> Select:
    return stmt.add_columns(*cols)


def security(db: Session, range_: str, node: str | None) -> dict[str, Any]:
    base, since = _base(range_, node)
    denied = base.where(_denied())

    hourly: dict[str, dict[str, int]] = defaultdict(dict)
    for hour, reason, n in db.execute(
        _with(denied, HOUR, LogEntry.reason, func.count()).group_by(HOUR, LogEntry.reason)
    ):
        group = "ip" if reason in ("ip", "ban", "internal") else reason
        group = group if group in ("mtls", "waf", "ip") else "other"
        hourly[hour][group] = hourly[hour].get(group, 0) + n

    top_ips = []
    for ip, n, country in db.execute(
        _with(denied, LogEntry.ip, func.count(), func.max(LogEntry.country))
        .group_by(LogEntry.ip)
        .order_by(func.count().desc())
        .limit(10)
    ):
        reasons = Counter(
            dict(
                db.execute(
                    _with(denied.where(LogEntry.ip == ip), LogEntry.reason, func.count()).group_by(
                        LogEntry.reason
                    )
                ).all()
            )
        )
        top_ips.append(
            {"ip": ip, "count": n, "country": country, "reason": reasons.most_common(1)[0][0]}
        )

    countries = [
        {"country": c, "count": n}
        for c, n in db.execute(
            _with(denied.where(LogEntry.country.is_not(None)), LogEntry.country, func.count())
            .group_by(LogEntry.country)
            .order_by(func.count().desc())
            .limit(30)
        )
    ]

    attacks: Counter[str] = Counter()
    rules: Counter[int] = Counter()
    blocked = 0
    for (waf_rules,) in db.execute(_with(base.where(LogEntry.reason == "waf"), LogEntry.waf_rules)):
        blocked += 1
        fams = {family(r) for r in waf_rules or [] if r < 949000}
        for f in fams or {"Sonstige"}:
            attacks[f] += 1
        for r in waf_rules or []:
            if r < 949000:
                rules[r] += 1

    by_host = []
    for host, total, mtls, waf, ip in db.execute(
        _with(
            denied,
            LogEntry.host,
            func.count(),
            func.sum(case((LogEntry.reason == "mtls", 1), else_=0)),
            func.sum(case((LogEntry.reason == "waf", 1), else_=0)),
            func.sum(case((LogEntry.reason.in_(("ip", "ban", "internal")), 1), else_=0)),
        )
        .group_by(LogEntry.host)
        .order_by(func.count().desc())
        .limit(10)
    ):
        by_host.append(
            {
                "host": host,
                "total": total,
                "mtls": mtls or 0,
                "waf": waf or 0,
                "ip": ip or 0,
                "other": total - (mtls or 0) - (waf or 0) - (ip or 0),
            }
        )

    total = db.scalar(_with(base, func.count())) or 0
    denied_total = db.scalar(_with(denied, func.count())) or 0
    # Bot-Schutz (Anubis): zur Prüfung geschickt (307), abgewiesen (sonst), Prüfung bestanden
    bot = {"challenged": 0, "denied": 0, "passed": 0}
    for code, n in db.execute(
        _with(base.where(LogEntry.reason == "bot"), LogEntry.status, func.count()).group_by(
            LogEntry.status
        )
    ):
        bot["challenged" if code == 307 else "denied"] += n
    bot["passed"] = (
        db.scalar(
            _with(
                base.where(
                    LogEntry.uri.like(ANUBIS_PASS + "%"),
                    LogEntry.status.between(300, 399),
                ),
                func.count(),
            )
        )
        or 0
    )
    return {
        "bot": bot,
        "since": since,
        "total": total,
        "denied": denied_total,
        "waf_blocked": blocked,
        "hourly": [{"t": h, **v} for h, v in sorted(hourly.items())],
        "top_ips": top_ips,
        "countries": countries,
        "attacks": [{"name": k, "count": v} for k, v in attacks.most_common()],
        "top_rules": [{"rule": k, "count": v} for k, v in rules.most_common(10)],
        "by_host": by_host,
    }


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    k = max(0, min(len(values) - 1, round(p * (len(values) - 1))))
    return round(values[k], 1)


def traffic(db: Session, range_: str, node: str | None) -> dict[str, Any]:
    base, since = _base(range_, node)
    passed = base.where(LogEntry.reason == "ok")

    hourly = defaultdict(lambda: {"ok": 0, "redirect": 0, "client": 0, "server": 0, "denied": 0})
    status_class = case(
        (LogEntry.status >= 500, 5),
        (LogEntry.status >= 400, 4),
        (LogEntry.status >= 300, 3),
        else_=2,
    )
    for hour, reason, status, n in db.execute(
        _with(base, HOUR, LogEntry.reason, status_class, func.count()).group_by(
            HOUR, LogEntry.reason, status_class
        )
    ):
        key = (
            "denied"
            if reason != "ok"
            else {2: "ok", 3: "redirect", 4: "client", 5: "server"}[status]
        )
        hourly[hour][key] += n

    composition = Counter()
    for v in hourly.values():
        composition.update(v)

    hosts = []
    rows = db.execute(
        _with(
            base,
            LogEntry.host,
            func.count(),
            func.sum(LogEntry.size),
            func.sum(case((LogEntry.status >= 500, 1), else_=0)),
            func.sum(case((LogEntry.reason != "ok", 1), else_=0)),
        )
        .group_by(LogEntry.host)
        .order_by(func.count().desc())
        .limit(50)
    ).all()
    for host, n, size, errors, denied in rows:
        durations = list(
            db.scalars(
                _with(passed.where(LogEntry.host == host), LogEntry.duration_ms)
                .order_by(LogEntry.id.desc())
                .limit(PERCENTILE_SAMPLE)
            )
        )
        served = n - (denied or 0)
        hosts.append(
            {
                "host": host,
                "requests": n,
                "bytes": size or 0,
                "median_ms": round(median(durations), 1) if durations else None,
                "p95_ms": _percentile(durations, 0.95),
                "errors": errors or 0,
                "denied": denied or 0,
                # Anteil der durchgelassenen Anfragen ohne 5xx
                "availability": round(100 * (served - (errors or 0)) / served, 2)
                if served
                else None,
            }
        )
    return {
        "since": since,
        "total": sum(composition.values()),
        "bytes": sum(h["bytes"] for h in hosts),
        "hourly": [{"t": h, **v} for h, v in sorted(hourly.items())],
        "composition": dict(composition),
        "hosts": hosts,
    }


def usage(db: Session, range_: str) -> dict[str, Any]:
    """Wer nutzt was – nur Anfragen mit erkanntem Gerätezertifikat."""
    base, since = _base(range_ if range_ in ("7d", "30d") else "7d", None)
    known = base.where(LogEntry.device_id.is_not(None))
    person_of = dict(db.execute(select(Device.id, Device.person_id)).all())
    names = dict(db.execute(select(Person.id, Person.name)).all())

    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    per_device: dict[int, dict[str, Any]] = {}
    for dev_id, host, n, size, last in db.execute(
        _with(
            known,
            LogEntry.device_id,
            LogEntry.host,
            func.count(),
            func.sum(LogEntry.size),
            func.max(LogEntry.ts),
        ).group_by(LogEntry.device_id, LogEntry.host)
    ):
        person = names.get(person_of.get(dev_id), "?")
        matrix[person][host] += n
        d = per_device.setdefault(
            dev_id, {"requests": 0, "bytes": 0, "last": last, "hosts": Counter()}
        )
        d["requests"] += n
        d["bytes"] += size or 0
        d["last"] = max(d["last"], last)
        d["hosts"][host] += n

    countries: dict[int, set[str]] = defaultdict(set)
    for dev_id, c in db.execute(
        _with(
            known.where(LogEntry.country.is_not(None)), LogEntry.device_id, LogEntry.country
        ).group_by(LogEntry.device_id, LogEntry.country)
    ):
        countries[dev_id].add(c)

    devices = []
    for dev in db.scalars(select(Device).where(Device.id.in_(per_device))):
        d = per_device[dev.id]
        devices.append(
            {
                "id": dev.id,
                "name": dev.name,
                "person": dev.person.name,
                "last": d["last"],
                "requests": d["requests"],
                "bytes": d["bytes"],
                "top_host": d["hosts"].most_common(1)[0][0],
                "countries": sorted(countries.get(dev.id, ())),
                "revoked": dev.revoked_at is not None,
            }
        )
    devices.sort(key=lambda d: d["requests"], reverse=True)

    hosts = sorted({h for c in matrix.values() for h in c})
    hourly = [
        {"t": h, "n": n} for h, n in db.execute(_with(known, HOUR, func.count()).group_by(HOUR))
    ]
    return {
        "since": since,
        "hosts": hosts,
        "matrix": [
            {"person": p, "counts": dict(c), "total": sum(c.values())}
            for p, c in sorted(matrix.items(), key=lambda x: -sum(x[1].values()))
        ],
        "hourly": sorted(hourly, key=lambda x: x["t"]),
        "devices": devices,
    }


# Karte: woher Anfragen kommen – alle, nur abgelehnte oder nur angenommene (Grund „ok“)
COUNTRY_FILTERS = ("all", "denied", "allowed")


def countries(db: Session, range_: str, node: str | None, which: str = "all") -> dict[str, Any]:
    base, since = _base(range_, node)
    sel = base.where(LogEntry.country.is_not(None))
    if which == "denied":
        sel = sel.where(_denied())
    elif which == "allowed":
        sel = sel.where(LogEntry.reason == "ok")
    rows = db.execute(
        _with(sel, LogEntry.country, func.count())
        .group_by(LogEntry.country)
        .order_by(func.count().desc(), LogEntry.country)
        .limit(60)
    )
    # ohne Land: private/lokale Adressen oder keine GeoIP-Datenbank
    total = base
    if which == "denied":
        total = total.where(_denied())
    elif which == "allowed":
        total = total.where(LogEntry.reason == "ok")
    out = [{"country": c, "count": n} for c, n in rows]
    all_n = db.scalar(_with(total, func.count())) or 0
    return {
        "since": since,
        "which": which,
        "countries": out,
        "unknown": all_n - sum(x["count"] for x in out),
    }
