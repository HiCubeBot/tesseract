"""Statistik aus Loki bzw. VictoriaLogs – gleiche Ausgabe wie `stats.py` (SQLite).

Jede Kennzahl ist eine Aggregat-Abfrage im externen Speicher; zusammengeführt wird hier.
"""

import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.db.models import Device, Person, utcnow
from tesseract.logstore import HOUR, Cond, Sel, denied
from tesseract.stats import RANGES, family


def _window(range_: str) -> tuple[datetime, datetime]:
    end = utcnow()
    return end - RANGES.get(range_, RANGES["24h"]), end


def _hour_key(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:00:00Z")


def _base(node: str | None) -> Sel:
    # Verbindungstests aus den Einstellungen nicht mitzählen
    s = Sel().add("reason", "ne", "test")
    if node:
        s.add("node", "eq", node)
    return s


def _with(s: Sel, *conds: Cond) -> Sel:
    out = s.copy()
    out.conds.extend(conds)
    return out


def _sum(rows) -> int:
    return int(sum(v for _, _, v in rows))


def _rules(raw: str) -> list[int]:
    try:
        return [int(r) for r in json.loads(raw or "[]")]
    except (ValueError, TypeError):
        return []


def security(store, range_: str, node: str | None) -> dict[str, Any]:
    start, end = _window(range_)
    base = _base(node)
    den = _with(base, denied())

    hourly: dict[str, dict[str, int]] = defaultdict(dict)
    for (reason,), t, n in store.count(den, start, end, ["reason"], HOUR):
        group = "ip" if reason in ("ip", "ban", "internal") else reason
        group = group if group in ("mtls", "waf", "ip") else "other"
        key = _hour_key(t)
        hourly[key][group] = hourly[key].get(group, 0) + int(n)

    # IPs: Anzahl je IP, Grund und Land in einer Abfrage, danach die zehn häufigsten
    per_ip: dict[str, Counter[str]] = defaultdict(Counter)
    country_of: dict[str, str] = {}
    for (ip, reason, country), _, n in store.count(den, start, end, ["ip", "reason", "country"]):
        per_ip[ip][reason] += int(n)
        if country:
            # wie SQLite (max): bei mehreren Ländern einer IP das „größte“
            country_of[ip] = max(country_of.get(ip, ""), country)
    top_ips = [
        {
            "ip": ip,
            "count": sum(c.values()),
            "country": country_of.get(ip),
            "reason": c.most_common(1)[0][0],
        }
        for ip, c in sorted(per_ip.items(), key=lambda x: -sum(x[1].values()))[:10]
    ]

    countries = sorted(
        (
            {"country": c, "count": int(n)}
            for (c,), _, n in store.count(den, start, end, ["country"])
            if c
        ),
        key=lambda x: -x["count"],
    )[:30]

    # WAF: Anzahl je Regel-Kombination (wenige verschiedene), dann aufgeteilt
    attacks: Counter[str] = Counter()
    rules: Counter[int] = Counter()
    blocked = 0
    waf = _with(base, Cond("reason", "eq", "waf"))
    for (raw,), _, n in store.count(waf, start, end, ["waf_rules"]):
        n = int(n)
        blocked += n
        rs = [r for r in _rules(raw) if r < 949000]
        for f in {family(r) for r in rs} or {"Sonstige"}:
            attacks[f] += n
        for r in rs:
            rules[r] += n

    per_host: dict[str, Counter[str]] = defaultdict(Counter)
    for (host, reason), _, n in store.count(den, start, end, ["host", "reason"]):
        per_host[host][reason] += int(n)
    by_host = []
    for host, c in sorted(per_host.items(), key=lambda x: (-sum(x[1].values()), x[0]))[:10]:
        total = sum(c.values())
        ip = c["ip"] + c["ban"] + c["internal"]
        by_host.append(
            {
                "host": "" if host == "-" else host,
                "total": total,
                "mtls": c["mtls"],
                "waf": c["waf"],
                "ip": ip,
                "other": total - c["mtls"] - c["waf"] - ip,
            }
        )

    return {
        "since": start,
        "total": _sum(store.count(base, start, end)),
        "denied": _sum(store.count(den, start, end)),
        "waf_blocked": blocked,
        "hourly": [{"t": h, **v} for h, v in sorted(hourly.items())],
        "top_ips": top_ips,
        "countries": countries,
        "attacks": [{"name": k, "count": v} for k, v in attacks.most_common()],
        "top_rules": [{"rule": k, "count": v} for k, v in rules.most_common(10)],
        "by_host": by_host,
    }


def _status_class(status: str) -> int:
    try:
        s = int(float(status))
    except ValueError:
        return 2
    return 5 if s >= 500 else 4 if s >= 400 else 3 if s >= 300 else 2


def traffic(store, range_: str, node: str | None) -> dict[str, Any]:
    start, end = _window(range_)
    base = _base(node)

    hourly = defaultdict(lambda: {"ok": 0, "redirect": 0, "client": 0, "server": 0, "denied": 0})
    for (reason, status), t, n in store.count(base, start, end, ["reason", "status"], HOUR):
        key = (
            "denied"
            if reason != "ok"
            else {2: "ok", 3: "redirect", 4: "client", 5: "server"}[_status_class(status)]
        )
        hourly[_hour_key(t)][key] += int(n)

    # Summen über das genaue Zeitfenster (die Stunden-Buckets beginnen zur vollen Stunde)
    composition: Counter[str] = Counter(
        {"ok": 0, "redirect": 0, "client": 0, "server": 0, "denied": 0}
    )
    per_host: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "errors": 0, "denied": 0})
    for (host, reason, status), _, n in store.count(base, start, end, ["host", "reason", "status"]):
        key = (
            "denied"
            if reason != "ok"
            else {2: "ok", 3: "redirect", 4: "client", 5: "server"}[_status_class(status)]
        )
        composition[key] += int(n)
        h = per_host[host]
        h["n"] += int(n)
        if _status_class(status) == 5:
            h["errors"] += int(n)
        if reason != "ok":
            h["denied"] += int(n)
    sizes = {k[0]: int(v) for k, _, v in store.total(base, start, end, "size", ["host"])}
    passed = _with(base, Cond("reason", "eq", "ok"))
    p50 = {k[0]: v for k, _, v in store.quantile(0.5, passed, start, end, "duration_ms", ["host"])}
    p95 = {k[0]: v for k, _, v in store.quantile(0.95, passed, start, end, "duration_ms", ["host"])}

    hosts = []
    for host, h in sorted(per_host.items(), key=lambda x: -x[1]["n"])[:50]:
        served = h["n"] - h["denied"]
        hosts.append(
            {
                "host": "" if host == "-" else host,
                "requests": h["n"],
                "bytes": sizes.get(host, 0),
                "median_ms": round(p50[host], 1) if host in p50 else None,
                "p95_ms": round(p95[host], 1) if host in p95 else None,
                "errors": h["errors"],
                "denied": h["denied"],
                "availability": round(100 * (served - h["errors"]) / served, 2) if served else None,
            }
        )
    return {
        "since": start,
        "total": sum(composition.values()),
        "bytes": sum(h["bytes"] for h in hosts),
        "hourly": [{"t": h, **v} for h, v in sorted(hourly.items())],
        "composition": dict(composition),
        "hosts": hosts,
    }


def usage(db: Session, store, range_: str) -> dict[str, Any]:
    """Wer nutzt was – nur Anfragen mit erkanntem Gerätezertifikat (Feld `device`)."""
    start, end = _window(range_ if range_ in ("7d", "30d") else "7d")
    known = Sel().add("reason", "ne", "test").add("device", "re", ".+")

    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    per_device: dict[tuple[str, str], dict[str, Any]] = {}
    pdh = ["person", "device", "host"]
    for (person, device, host), _, n in store.count(known, start, end, pdh):
        n = int(n)
        matrix[person or "?"][host] += n
        d = per_device.setdefault((person, device), {"requests": 0, "hosts": Counter()})
        d["requests"] += n
        d["hosts"][host] += n
    pd = ["person", "device"]
    sizes = {(k[0], k[1]): int(v) for k, _, v in store.total(known, start, end, "size", pd)}
    countries: dict[tuple[str, str], set[str]] = defaultdict(set)
    for (person, device, c), _, _n in store.count(known, start, end, [*pd, "country"]):
        if c:
            countries[(person, device)].add(c)

    # Geräte über Person + Name zuordnen (die Logs kennen nur Namen)
    by_name = {
        (p.name, d.name): d
        for d, p in db.execute(select(Device, Person).join(Person, Device.person_id == Person.id))
    }
    devices = []
    for key, d in per_device.items():
        dev = by_name.get(key)
        devices.append(
            {
                "id": dev.id if dev else 0,
                "name": key[1],
                "person": key[0] or "?",
                "last": dev.last_seen_at if dev and dev.last_seen_at else None,
                "requests": d["requests"],
                "bytes": sizes.get(key, 0),
                "top_host": d["hosts"].most_common(1)[0][0],
                "countries": sorted(countries.get(key, ())),
                "revoked": bool(dev and dev.revoked_at is not None),
            }
        )
    devices.sort(key=lambda d: d["requests"], reverse=True)

    hourly: Counter[str] = Counter()
    for _, t, n in store.count(known, start, end, [], HOUR):
        hourly[_hour_key(t)] += int(n)
    hosts = sorted({h for c in matrix.values() for h in c})
    return {
        "since": start,
        "hosts": hosts,
        "matrix": [
            {"person": p, "counts": dict(c), "total": sum(c.values())}
            for p, c in sorted(matrix.items(), key=lambda x: -sum(x[1].values()))
        ],
        "hourly": [{"t": t, "n": n} for t, n in sorted(hourly.items())],
        "devices": devices,
    }
