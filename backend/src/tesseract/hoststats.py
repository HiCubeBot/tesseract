"""Statistik eines einzelnen Hosts und Aktivität aller Hosts (letzte 24 h).

Läuft über die gemeinsame Abfrage-Schnittstelle (`SqlStore` bzw. Loki/VictoriaLogs), damit
dieselbe Auswertung mit jedem Log-Speicher funktioniert. Zeitreihen werden stündlich geholt
und hier auf die Anzeige-Schritte (Stunde, 6 Stunden, Tag; in UTC) zusammengefasst.
"""

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import median
from typing import Any

from tesseract.db.models import utcnow
from tesseract.logstore import HOUR, Cond, Sel, denied
from tesseract.sqlstore import BOT_PATTERN

RANGES = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}

# Pfad-Segmente, die nur IDs sind → zusammenfassen
_ID_SEGMENT = re.compile(
    r"^(\d+|[0-9a-f]{16,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$", re.I
)
_ASSET = re.compile(
    r"\.(png|jpe?g|gif|svg|webp|avif|ico|css|js|mjs|map|woff2?|ttf|mp4|webm)$", re.I
)


def path_key(uri: str) -> str:
    """URI → zusammengefasster Pfad: ohne Query, IDs als `*`, Bilder & Co. als `*.png`."""
    path = (uri or "/").split("?", 1)[0].split("#", 1)[0] or "/"
    parts = path.split("/")
    out = []
    for i, seg in enumerate(parts):
        if _ID_SEGMENT.match(seg):
            out.append("*")
        elif i == len(parts) - 1 and (m := _ASSET.search(seg)):
            out.append("*." + m.group(1).lower())
        else:
            out.append(seg)
    return "/".join(out)[:200] or "/"


def _sel(domain: str) -> Sel:
    return Sel().add("host", "eq", domain).add("reason", "ne", "test")


def _with(s: Sel, *conds: Cond) -> Sel:
    out = s.copy()
    out.conds.extend(conds)
    return out


def _sum(rows) -> float:
    return sum(v for _, _, v in rows)


def _buckets(start: datetime, end: datetime, step: timedelta) -> list[datetime]:
    """Bucket-Anfänge, ausgerichtet an der Epoche (wie `strftime('%s')/step` in SQLite)."""
    s = int(step.total_seconds())
    t0 = int(start.timestamp()) // s * s
    out = []
    t = t0
    while t < end.timestamp():
        out.append(datetime.fromtimestamp(t, start.tzinfo))
        t += s
    return out


def _series(rows, start: datetime, end: datetime, step: timedelta, shift=timedelta(0)):
    """[(…, t, v)] → Werte je Bucket (fehlende = 0). `shift` verschiebt (Vorzeitraum)."""
    buckets = _buckets(start, end, step)
    if not buckets:
        return []
    s = step.total_seconds()
    t0 = buckets[0].timestamp()
    values = [0.0] * len(buckets)
    for _, t, v in rows:
        if t is None:
            continue
        i = int(((t + shift).timestamp() - t0) // s)
        if 0 <= i < len(values):
            values[i] += v
    return values


def _median_series(rows, start, end, step) -> list[float | None]:
    """Stündliche Mediane → je Anzeige-Bucket der Median davon."""
    buckets = _buckets(start, end, step)
    if not buckets:
        return []
    s = step.total_seconds()
    t0 = buckets[0].timestamp()
    groups: dict[int, list[float]] = defaultdict(list)
    for _, t, v in rows:
        if t is not None:
            groups[int((t.timestamp() - t0) // s)].append(v)
    return [round(median(groups[i]), 1) if groups.get(i) else None for i in range(len(buckets))]


def _first(rows) -> float | None:
    return rows[0][2] if rows else None


def _pct(part: float, whole: float) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def host(store, domain: str, range_: str) -> dict[str, Any]:
    span = RANGES.get(range_, RANGES["24h"])
    step = HOUR  # stündlich – das Frontend fasst in Ortszeit zusammen
    end = utcnow()
    start = end - span
    prev = start - span

    base = _sel(domain)
    ok = _with(base, Cond("reason", "eq", "ok"))
    human = _with(ok, Cond("user_agent", "nire", BOT_PATTERN))
    den = _with(base, denied())

    # Anfragen (stündlich, auch für den Vorzeitraum)
    cur_rows = store.count(base, start, end, [], HOUR)
    prev_rows = store.count(base, prev, start, [], HOUR)
    requests = _series(cur_rows, start, end, step)
    previous = _series(prev_rows, start, end, step, shift=span)

    # Besucher: verschiedene IPs ohne Bots
    visitors_rows = store.count(human, start, end, ["ip"])
    prev_visitors = len(store.count(human, prev, start, ["ip"]))
    # je Stunde verschiedene IPs (für die Verlaufslinie)
    visitor_series = _series(
        [((), t, 1.0) for _, t, _ in store.count(human, start, end, ["ip"], step)],
        start,
        end,
        step,
    )

    # Daten
    bytes_out_rows = store.total(base, start, end, "size", [], HOUR)
    bytes_out = _sum(bytes_out_rows)
    bytes_in = _sum(store.total(base, start, end, "bytes_in"))
    prev_bytes = _sum(store.total(base, prev, start, "size"))

    # Antwortzeit (nur durchgelassene Anfragen)
    med = _first(store.quantile(0.5, ok, start, end, "duration_ms"))
    p95 = _first(store.quantile(0.95, ok, start, end, "duration_ms"))
    prev_med = _first(store.quantile(0.5, ok, prev, start, "duration_ms"))
    med_series = _median_series(
        store.quantile(0.5, ok, start, end, "duration_ms", [], step), start, end, step
    )

    # Serverfehler und Kompression
    served = _sum(store.count(ok, start, end))
    errors = _sum(store.count(_with(ok, Cond("status", "gte", 500)), start, end))
    enc: Counter[str] = Counter()
    for (e,), _, n in store.count(_with(ok, Cond("status", "eq", 200)), start, end, ["encoding"]):
        enc[e or ""] += int(n)
    compressible = sum(enc.values())
    compressed = sum(n for e, n in enc.items() if e and e != "identity")

    # Abgelehnt je Stunde nach Grund
    denied_rows = store.count(den, start, end, ["reason"], HOUR)
    groups: dict[str, list] = defaultdict(list)
    for (reason,), t, n in denied_rows:
        g = "ip" if reason in ("ip", "ban", "internal") else reason
        groups[g if g in ("mtls", "waf", "ip") else "other"].append(((), t, n))
    denied_series = {g: _series(rows, start, end, step) for g, rows in groups.items()}

    # Herkunft: Anfragen und davon abgelehnt je Land
    countries: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "denied": 0})
    for (country, reason), _, n in store.count(base, start, end, ["country", "reason"]):
        c = countries[country or ""]
        c["count"] += int(n)
        if reason != "ok":
            c["denied"] += int(n)
    unknown = countries.pop("", {"count": 0})["count"]

    # Pfade (zusammengefasst)
    paths: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "errors": 0, "denied": 0})
    for (uri, reason, status), _, n in store.count(base, start, end, ["uri", "reason", "status"]):
        p = paths[path_key(uri)]
        p["count"] += int(n)
        if reason != "ok":
            p["denied"] += int(n)
        elif _int(status) >= 500:
            p["errors"] += int(n)

    # Abgelehnte IPs
    per_ip: dict[str, Counter[str]] = defaultdict(Counter)
    country_of: dict[str, str] = {}
    for (ip, reason, country), _, n in store.count(den, start, end, ["ip", "reason", "country"]):
        per_ip[ip][reason] += int(n)
        if country:
            country_of[ip] = country

    total = _sum(cur_rows)
    bytes_series = _series(bytes_out_rows, start, end, step)
    hourly = []
    for i, b in enumerate(_buckets(start, end, step)):
        row: dict[str, Any] = {
            "t": b.strftime("%Y-%m-%dT%H:00:00Z"),
            "requests": int(requests[i]),
            "previous": int(previous[i]),
            "visitors": int(visitor_series[i]),
            "bytes": int(bytes_series[i]),
            "latency": med_series[i],
        }
        for g, vs in denied_series.items():
            row[g] = int(vs[i])
        hourly.append(row)
    return {
        "host": domain,
        "range": range_,
        "since": start,
        "requests": {"total": int(total), "previous": int(_sum(prev_rows))},
        "visitors": {"total": len(visitors_rows), "previous": prev_visitors},
        "bytes": {"out": int(bytes_out), "in": int(bytes_in), "previous": int(prev_bytes)},
        "latency": {"median": _round(med), "p95": _round(p95), "previous": _round(prev_med)},
        "errors": {"count": int(errors), "share": _pct(errors, served) or 0.0},
        "compression": {
            "share": _pct(compressed, compressible),
            "encodings": [e for e, _ in enc.most_common() if e and e != "identity"],
        },
        "hourly": hourly,
        "denied": int(sum(sum(v) for v in denied_series.values())),
        "countries": sorted(
            ({"country": k, **v} for k, v in countries.items()), key=lambda x: -x["count"]
        )[:15],
        "unknown_country": unknown,
        "paths": sorted(({"path": k, **v} for k, v in paths.items()), key=lambda x: -x["count"])[
            :25
        ],
        "top_denied_ips": [
            {
                "ip": ip,
                "count": sum(c.values()),
                "reason": c.most_common(1)[0][0],
                "country": country_of.get(ip),
            }
            for ip, c in sorted(per_ip.items(), key=lambda x: -sum(x[1].values()))[:10]
        ],
    }


def activity(store) -> dict[str, Any]:
    """Anfragen der letzten 24 Stunden je Host, stündlich (für die Hostliste)."""
    end = utcnow()
    start = end - timedelta(hours=24)
    per_host: dict[str, list] = defaultdict(list)
    for (h,), t, n in store.count(Sel().add("reason", "ne", "test"), start, end, ["host"], HOUR):
        per_host[h].append(((), t, n))
    hosts = {}
    for h, rows in per_host.items():
        series = [int(v) for v in _series(rows, start, end, HOUR)]
        hosts[h] = {"total": sum(series), "hourly": series}
    return {"since": start, "hosts": hosts}


def _int(v: Any) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _round(v: float | None) -> float | None:
    return round(v, 1) if v is not None else None
