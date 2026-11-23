"""Erweiterte Statistik (ab 1.16): Kennzahlen mit Vorzeitraum, Zusammensetzung, Clients,
Statuscodes, Pfade, Herkunft mit Städten und Netzbetreibern, gesamter Zeitraum.

Alles über die gemeinsame Abfrage-Schnittstelle (`SqlStore` bzw. Loki/VictoriaLogs). Der
gesamte Zeitraum kommt aus den verdichteten Tageswerten (`rollup`).
"""

import ipaddress
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tesseract.clients import classify
from tesseract.db.models import AuditEntry, StatsDaily, StatsHourly, VisitorIp, utcnow
from tesseract.hoststats import path_key
from tesseract.logstore import HOUR, Cond, Sel, denied
from tesseract.sqlstore import BOT_PATTERN

RANGES = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}

STATUS_TEXT = {
    "200": "OK",
    "201": "angelegt",
    "204": "ohne Inhalt",
    "206": "teilweise",
    "301": "dauerhaft umgeleitet",
    "302": "umgeleitet",
    "304": "nicht geändert",
    "307": "umgeleitet",
    "308": "dauerhaft umgeleitet",
    "400": "fehlerhafte Anfrage",
    "401": "Anmeldung nötig",
    "403": "abgewiesen",
    "404": "nicht gefunden",
    "405": "Methode nicht erlaubt",
    "413": "zu groß",
    "429": "zu viele Anfragen",
    "499": "abgebrochen",
    "500": "Serverfehler",
    "502": "Ziel nicht erreichbar",
    "503": "nicht verfügbar",
    "504": "Zeitüberschreitung",
}


def _window(range_: str) -> tuple[datetime, datetime, datetime, timedelta]:
    span = RANGES.get(range_, RANGES["24h"])
    end = utcnow()
    return end - span, end, end - 2 * span, span


def _base(node: str | None, host: str | None = None) -> Sel:
    s = Sel().add("reason", "ne", "test")
    if node:
        s.add("node", "eq", node)
    if host:
        s.add("host", "eq", host)
    return s


def _with(s: Sel, *conds: Cond) -> Sel:
    out = s.copy()
    out.conds.extend(conds)
    return out


def _sum(rows) -> int:
    return int(sum(v for _, _, v in rows))


def _hour_key(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:00:00Z")


def _first(rows) -> float | None:
    return round(rows[0][2], 1) if rows else None


def _pct(part: float, whole: float) -> float | None:
    return round(100 * part / whole, 2) if whole else None


def _in_any(ip: str, nets: list) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in n for n in nets)


# ---------- Sicherheit ----------


def security_extra(
    store,
    db: Session,
    range_: str,
    node: str | None,
    client_ip: str | None = None,
    internal: list[str] = (),
) -> dict[str, Any]:
    start, end, prev, _ = _window(range_)
    base = _base(node)
    den = _with(base, denied())

    hourly: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "denied": 0})
    for _, t, n in store.count(base, start, end, [], HOUR):
        hourly[_hour_key(t)]["total"] += int(n)
    for (reason,), t, n in store.count(den, start, end, ["reason"], HOUR):
        h = hourly[_hour_key(t)]
        h["denied"] += int(n)
        g = "ip" if reason in ("ip", "ban", "internal") else reason
        g = g if g in ("mtls", "waf", "ip") else "other"
        h[g] = h.get(g, 0) + int(n)

    # WAF im Modus „nur protokollieren“: Regeln ausgelöst, Anfrage aber durchgelassen
    detected = _sum(
        store.count(
            _with(base, Cond("reason", "eq", "ok"), Cond("waf_rules", "re", ".*[0-9].*")),
            start,
            end,
        )
    )

    # Fehlanmeldungen an der Oberfläche (Audit-Log, nur Controller)
    failed: Counter[str] = Counter()
    for (ts,) in db.execute(
        select(AuditEntry.created_at).where(
            AuditEntry.action == "login_failed", AuditEntry.created_at >= start
        )
    ):
        failed[_hour_key(ts)] += 1
    for k, n in failed.items():
        hourly[k]["login_failed"] = n

    # Top abgelehnte IPs mit Kennzeichen „eigene“ (Geräte mit Zertifikat, eigene Sitzung)
    # und „intern“ (interne Netze)
    own = {
        ip
        for (ip,), _, _ in store.count(_with(base, Cond("device", "re", ".+")), start, end, ["ip"])
    }
    if client_ip:
        own.add(client_ip)
    nets = []
    for n in internal:
        try:
            nets.append(ipaddress.ip_network(n, strict=False))
        except ValueError:
            continue
    per_ip: dict[str, Counter[str]] = defaultdict(Counter)
    where: dict[str, tuple[str, str]] = {}
    for (ip, reason, country, city), _, n in store.count(
        den, start, end, ["ip", "reason", "country", "city"]
    ):
        per_ip[ip][reason] += int(n)
        if country or city:
            where[ip] = (country, city)
    top = []
    for ip, c in sorted(per_ip.items(), key=lambda x: (-sum(x[1].values()), x[0]))[:15]:
        country, city = where.get(ip, ("", ""))
        top.append(
            {
                "ip": ip,
                "count": sum(c.values()),
                "reason": c.most_common(1)[0][0],
                "country": country or None,
                "city": city or None,
                "own": ip in own,
                "internal": _in_any(ip, nets),
            }
        )

    return {
        "previous": {
            "total": _sum(store.count(base, prev, start)),
            "denied": _sum(store.count(den, prev, start)),
        },
        "waf_detected": detected,
        "login_failed": sum(failed.values()),
        "hourly_all": [{"t": k, **v} for k, v in sorted(hourly.items())],
        "top_ips_flagged": top,
    }


# ---------- Traffic ----------


def _composition(codes: Counter, proto: Counter, kinds: Counter) -> dict[str, Any]:
    total = sum(codes.values()) or 1
    by_class = Counter()
    for code, n in codes.items():
        c = str(code)[:1]
        by_class[c if c in "2345" else "?"] += n
    ptotal = sum(proto.values()) or 1
    ktotal = sum(kinds.values()) or 1
    return {
        "status": {k: round(100 * by_class[k] / total, 1) for k in "2345"},
        "proto": {k: round(100 * proto[k] / ptotal, 1) for k in ("3", "2", "1.1")},
        "clients": {k: round(100 * kinds[k] / ktotal, 1) for k in ("browser", "app", "bot")},
    }


def _clients(ua_rows) -> tuple[Counter, list[dict[str, Any]]]:
    kinds: Counter[str] = Counter()
    names: Counter[tuple[str, str]] = Counter()
    for (ua,), _, n in ua_rows:
        kind, name = classify(ua)
        kinds[kind] += int(n)
        names[(name, kind)] += int(n)
    return kinds, [
        {"name": name, "kind": kind, "count": n} for (name, kind), n in names.most_common(15)
    ]


def traffic_extra(store, range_: str, node: str | None, host: str | None = None):
    start, end, prev, _ = _window(range_)
    base = _base(node, host)
    ok = _with(base, Cond("reason", "eq", "ok"))
    human = _with(ok, Cond("user_agent", "nire", BOT_PATTERN))

    hourly: dict[str, dict[str, float]] = defaultdict(lambda: {"requests": 0, "previous": 0})
    for _, t, n in store.count(base, start, end, [], HOUR):
        hourly[_hour_key(t)]["requests"] += n
    for _, t, n in store.count(base, prev, start, [], HOUR):
        hourly[_hour_key(t + (start - prev))]["previous"] += n
    for _, t, n in store.total(base, start, end, "size", [], HOUR):
        hourly[_hour_key(t)]["bytes"] = n
    for _, t, _n in store.count(human, start, end, ["ip"], HOUR):
        h = hourly[_hour_key(t)]
        h["visitors"] = h.get("visitors", 0) + 1
    for _, t, v in store.quantile(0.5, ok, start, end, "duration_ms", [], HOUR):
        hourly[_hour_key(t)]["latency"] = round(v, 1)
    for _, t, n in store.count(_with(ok, Cond("status", "gte", 500)), start, end, [], HOUR):
        hourly[_hour_key(t)]["errors"] = n

    codes: Counter[str] = Counter()
    for (status,), _, n in store.count(base, start, end, ["status"]):
        codes[str(int(float(status or 0)))] += int(n)
    proto: Counter[str] = Counter()
    for (p,), _, n in store.count(base, start, end, ["proto"]):
        if p:
            proto["1.1" if p in ("1.0", "1.1") else p] += int(n)
    kinds, clients = _clients(store.count(base, start, end, ["user_agent"]))

    served = _sum(store.count(ok, start, end))
    errors = _sum(store.count(_with(ok, Cond("status", "gte", 500)), start, end))
    enc: Counter[str] = Counter()
    for (e,), _, n in store.count(_with(ok, Cond("status", "eq", 200)), start, end, ["encoding"]):
        enc[e or ""] += int(n)
    compressible = sum(enc.values())
    compressed = sum(n for e, n in enc.items() if e and e != "identity")

    # Pfade: aufgerufen und mit Fehlern (5xx oder 4xx ohne Ablehnung durch Tesseract)
    paths: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"count": 0, "errors": 0, "client_errors": 0}
    )
    for (h, uri, reason, status), _, n in store.count(
        base, start, end, ["host", "uri", "reason", "status"]
    ):
        p = paths[(h, path_key(uri))]
        p["count"] += int(n)
        s = int(float(status or 0))
        if reason == "ok" and s >= 500:
            p["errors"] += int(n)
        elif reason == "ok" and s >= 400:
            p["client_errors"] += int(n)
    path_list = [{"host": h, "path": k, **v} for (h, k), v in paths.items()]

    total = sum(codes.values())
    lat = _first(store.quantile(0.5, ok, start, end, "duration_ms"))
    return {
        "kpi": {
            "requests": total,
            "requests_prev": _sum(store.count(base, prev, start)),
            "visitors": len(store.count(human, start, end, ["ip"])),
            "visitors_prev": len(store.count(human, prev, start, ["ip"])),
            "bytes_out": _sum(store.total(base, start, end, "size")),
            "bytes_out_prev": _sum(store.total(base, prev, start, "size")),
            "bytes_in": _sum(store.total(base, start, end, "bytes_in")),
            "latency": lat,
            "latency_prev": _first(store.quantile(0.5, ok, prev, start, "duration_ms")),
            "latency_p95": _first(store.quantile(0.95, ok, start, end, "duration_ms")),
            "errors": errors,
            "errors_share": _pct(errors, served) or 0.0,
            "errors_top_host": _top_error_host(path_list),
            "compressed_share": _pct(compressed, compressible),
            "encodings": [e for e, _ in enc.most_common() if e and e != "identity"],
        },
        "series": [{"t": k, **v} for k, v in sorted(hourly.items())],
        "mix": _composition(codes, proto, kinds),
        "clients": clients,
        "status_codes": [
            {"code": c, "text": STATUS_TEXT.get(c, ""), "count": n}
            for c, n in codes.most_common(12)
            if c != "0"
        ],
        "paths_top": sorted(path_list, key=lambda x: -x["count"])[:15],
        "paths_errors": sorted(
            (p for p in path_list if p["errors"] or p["client_errors"]),
            key=lambda x: -(x["errors"] * 10 + x["client_errors"]),
        )[:15],
    }


def _top_error_host(paths: list[dict[str, Any]]) -> str | None:
    c: Counter[str] = Counter()
    for p in paths:
        c[p["host"]] += p["errors"]
    top = c.most_common(1)
    return top[0][0] if top and top[0][1] else None


# ---------- Gesamter Zeitraum (aus den Tageswerten) ----------


def traffic_all(db: Session, node: str | None, host: str | None = None) -> dict[str, Any]:
    from tesseract.rollup import day_values

    stmt = select(StatsDaily)
    if node:
        stmt = stmt.where(StatsDaily.node == node)
    if host:
        stmt = stmt.where(StatsDaily.host == host)
    rows = [_row_dict(r) for r in db.scalars(stmt)]
    # heute (noch nicht verdichtet) dazu
    today, _, _ = day_values(db, utcnow().date())
    rolled_days = {r["day"] for r in rows}
    rows += [
        r
        for r in today
        if (not node or r["node"] == node)
        and (not host or r["host"] == host)
        and r["day"] not in rolled_days
    ]
    if not rows:
        return {"kpi": {"requests": 0}, "series": [], "since": None, "days": 0}

    tot: Counter[str] = Counter()
    codes: Counter[str] = Counter()
    clients: Counter[str] = Counter()
    per_month: dict[str, Counter[str]] = defaultdict(Counter)
    per_day: dict[str, Counter[str]] = defaultdict(Counter)
    days = set()
    medians = []
    kinds_by_name: dict[str, str] = {}
    for r in rows:
        days.add(r["day"])
        for k in [
            "requests",
            "denied",
            "bytes_out",
            "bytes_in",
            "s2xx",
            "s3xx",
            "s4xx",
            "s5xx",
            "http1",
            "http2",
            "http3",
            "browser",
            "app",
            "bot",
            "compressed",
            "compressible",
        ]:
            tot[k] += r[k] or 0
        codes.update(r["codes"] or {})
        clients.update(r["clients"] or {})
        m = r["day"][:7]
        per_month[m]["requests"] += r["requests"]
        per_month[m]["bytes"] += r["bytes_out"]
        per_month[m]["errors"] += r["s5xx"]
        per_day[r["day"]]["requests"] += r["requests"]
        per_day[r["day"]]["bytes"] += r["bytes_out"]
        per_day[r["day"]]["errors"] += r["s5xx"]
        if r["median_ms"] is not None:
            medians.append(r["median_ms"])
    for key in clients:
        kind, _, name = key.partition(":")
        kinds_by_name[key] = kind if name else classify(key)[0]
    first = min(days)
    served = tot["requests"] - tot["denied"]
    error_host = Counter()
    for r in rows:
        error_host[r["host"]] += r["s5xx"]
    top_err = error_host.most_common(1)
    visitors = db.scalar(select(func.count()).select_from(VisitorIp)) or 0
    kinds = Counter({"browser": tot["browser"], "app": tot["app"], "bot": tot["bot"]})
    proto = Counter({"3": tot["http3"], "2": tot["http2"], "1.1": tot["http1"]})
    return {
        "since": first,
        "days": len(days),
        "kpi": {
            "requests": tot["requests"],
            "visitors": visitors,
            "bytes_out": tot["bytes_out"],
            "bytes_in": tot["bytes_in"],
            "latency": round(median(medians), 1) if medians else None,
            "errors": tot["s5xx"],
            "errors_share": _pct(tot["s5xx"], served) or 0.0,
            "errors_top_host": top_err[0][0] if top_err and top_err[0][1] else None,
            "compressed_share": _pct(tot["compressed"], tot["compressible"]),
            "encodings": [],
        },
        "months": [{"t": m, **v} for m, v in sorted(per_month.items())],
        # bei kurzer Aufzeichnung zeigt das Diagramm Tage statt Monate
        "days_series": [{"t": d, **v} for d, v in sorted(per_day.items())][-120:],
        "mix": _composition(codes, proto, kinds),
        "clients": [
            {"name": n.partition(":")[2] or n, "kind": kinds_by_name.get(n, "app"), "count": c}
            for n, c in clients.most_common(15)
        ],
        "status_codes": [
            {"code": c, "text": STATUS_TEXT.get(c, ""), "count": n}
            for c, n in codes.most_common(12)
            if c != "0"
        ],
    }


def _row_dict(r: StatsDaily) -> dict[str, Any]:
    return {c.name: getattr(r, c.name) for c in StatsDaily.__table__.columns}


# ---------- Rekorde ----------


def records(db: Session) -> dict[str, Any]:
    """Stärkster Tag, stärkste Stunde, meiste Daten an einem Tag, größte Abweisungswelle."""
    per_day: dict[str, Counter[str]] = defaultdict(Counter)
    top_host_day: dict[str, Counter[str]] = defaultdict(Counter)
    for r in db.scalars(select(StatsDaily)):
        per_day[r.day]["requests"] += r.requests
        per_day[r.day]["bytes"] += r.bytes_out
        top_host_day[r.day][r.host] += r.requests
    out: dict[str, Any] = {}
    if per_day:
        d = max(per_day, key=lambda k: per_day[k]["requests"])
        out["day"] = {
            "day": d,
            "requests": per_day[d]["requests"],
            "host": top_host_day[d].most_common(1)[0][0],
        }
        b = max(per_day, key=lambda k: per_day[k]["bytes"])
        out["bytes_day"] = {"day": b, "bytes": per_day[b]["bytes"]}
    h = db.scalar(select(StatsHourly).order_by(StatsHourly.requests.desc()).limit(1))
    if h:
        out["hour"] = {"hour": h.hour, "requests": h.requests, "host": h.top_host}
    w = db.scalar(select(StatsHourly).order_by(StatsHourly.denied.desc()).limit(1))
    if w and w.denied:
        out["denied_hour"] = {"hour": w.hour, "denied": w.denied, "host": w.top_denied_host}
    first = db.scalar(select(func.min(StatsDaily.day)))
    out["since"] = first
    return out


# ---------- Herkunft (Karte) ----------


def geo(store, range_: str, node: str | None, which: str = "all") -> dict[str, Any]:
    start, end, _, _ = _window(range_)
    sel = _base(node)
    if which == "denied":
        sel = _with(sel, denied())
    elif which == "allowed":
        sel = _with(sel, Cond("reason", "eq", "ok"))
    countries: Counter[str] = Counter()
    unknown = 0
    cities: Counter[tuple] = Counter()
    for (country, city, lat, lon), _, n in store.count(
        sel, start, end, ["country", "city", "lat", "lon"]
    ):
        n = int(n)
        if not country:
            unknown += n
            continue
        countries[country] += n
        if city and lat not in (None, "") and lon not in (None, ""):
            cities[(country, city, round(float(lat), 2), round(float(lon), 2))] += n
    asns: Counter[tuple] = Counter()
    for (asn, org), _, n in store.count(sel, start, end, ["asn", "as_org"]):
        if asn not in (None, "", "0"):
            asns[(int(float(asn)), org or "")] += int(n)
    return {
        "since": start,
        "which": which,
        "countries": [{"country": c, "count": n} for c, n in countries.most_common(200)],
        "cities": [
            {"country": c, "city": ci, "lat": la, "lon": lo, "count": n}
            for (c, ci, la, lo), n in cities.most_common(500)
        ],
        "asns": [{"asn": a, "org": o, "count": n} for (a, o), n in asns.most_common(50)],
        "unknown": unknown,
    }
