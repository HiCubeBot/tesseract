"""Logs und Statistik direkt aus Loki oder VictoriaLogs lesen.

Ist in den Einstellungen „Log-Ansicht und Statistik aus Loki/VictoriaLogs“ eingeschaltet,
fragen die Log-Ansicht und die Statistik den externen Speicher statt SQLite – damit reichen
sie so weit zurück, wie Loki bzw. VictoriaLogs aufbewahrt (SQLite nur `logs_days`).

Die Einträge kommen so an, wie `loki.py` sie schreibt: Labels bzw. Stream-Felder `job`,
`node`, `host`, `reason`, alles andere als JSON-Felder.

- Suche: dieselbe Filtersyntax wie in SQLite (`host:git status:4xx ip:… rule:942100 …`),
  übersetzt nach LogQL bzw. LogsQL.
- IDs: externe Einträge haben keine Datenbank-ID. Als ID dient der Zeitstempel in
  Mikrosekunden – damit funktionieren Blättern (`before_id`), Live (`after_id`) und die
  Detailansicht unverändert. (Nanosekunden passen nicht verlustfrei in JavaScript-Zahlen.)
- Statistik: Aggregat-Abfragen (`sum by … count_over_time` bzw. `| stats by …`), nicht das
  Herunterladen aller Einträge.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from tesseract.loki import _vl_headers

# Felder der JSON-Zeile (alles außer den Labels)
LABELS = ("node", "host", "reason")
NUMERIC = ("status", "duration_ms", "size", "waf_score")
HOUR = timedelta(hours=1)


class StoreError(Exception):
    pass


# ---------- Bedingungen ----------


@dataclass
class Cond:
    """Eine Bedingung auf ein Feld. op: eq | ne | in | gte | lt | re | ire | cidr | rule"""

    field: str
    op: str
    value: Any


@dataclass
class Sel:
    """UND-verknüpfte Bedingungen; `any_of` sind zusätzlich ODER-Gruppen (jede muss passen)."""

    conds: list[Cond] = field(default_factory=list)
    any_of: list[list[Cond]] = field(default_factory=list)

    def add(self, f: str, op: str, value: Any) -> "Sel":
        self.conds.append(Cond(f, op, value))
        return self

    def copy(self) -> "Sel":
        return Sel(list(self.conds), [list(g) for g in self.any_of])

    def fields(self) -> set[str]:
        out = {c.field for c in self.conds}
        for g in self.any_of:
            out |= {c.field for c in g}
        return out


def sel_from_query(q: str, filter_name: str = "all") -> Sel:
    """Filtersyntax der Log-Ansicht → Bedingungen (gleiche Bedeutung wie `logs.apply_query`)."""
    import ipaddress
    import shlex

    from tesseract.logs import FILTERS, SEARCH_KEYS, QueryError

    s = Sel()
    try:
        tokens = shlex.split(q or "")
    except ValueError as e:
        raise QueryError("Anführungszeichen nicht geschlossen") from e
    for tok in tokens:
        key, sep, value = tok.partition(":")
        key = key.lower()
        if not sep or key not in SEARCH_KEYS:
            text = re.escape(tok)
            s.any_of.append([Cond("uri", "ire", text), Cond("host", "ire", text)])
            continue
        if not value:
            raise QueryError(f"„{key}:“ ohne Wert")
        if key == "host":
            s.add("host", "re", re.escape(value.lower()) + r"(\..*)?")
        elif key == "node":
            s.add("node", "eq", value)
        elif key == "status":
            v = value.lower()
            if re.fullmatch(r"[1-5]xx", v):
                base = int(v[0]) * 100
                s.add("status", "gte", base).add("status", "lt", base + 100)
            elif v.isdigit():
                s.add("status", "eq", int(v))
            else:
                raise QueryError("status: Zahl oder z. B. 4xx")
        elif key == "ip":
            if "/" in value:
                try:
                    net = ipaddress.ip_network(value, strict=False)
                except ValueError as e:
                    raise QueryError(f"ip: {value} ist kein Netz") from e
                s.add("ip", "cidr", str(net))
            else:
                s.add("ip", "eq", value)
        elif key == "reason":
            s.add("reason", "eq", value.lower())
        elif key == "rule":
            if not value.isdigit():
                raise QueryError("rule: Regel-ID als Zahl")
            s.add("waf_rules", "rule", int(value))
        elif key == "method":
            s.add("method", "eq", value.upper())
        elif key == "country":
            s.add("country", "eq", value.upper())
        elif key == "device":
            s.add("device", "ire", re.escape(value))
    f = FILTERS.get(filter_name)
    if f == "denied":
        s.any_of.append([Cond("reason", "ne", "ok"), Cond("status", "gte", 400)])
    elif f:
        s.add("reason", "in", list(f))
    return s


DENIED = ("waf", "ip", "ban", "mtls", "internal", "websocket", "authelia")


def denied() -> Cond:
    return Cond("reason", "in", list(DENIED))


# ---------- Hilfen ----------


def to_id(ts: datetime) -> int:
    """Zeitstempel → ID (Mikrosekunden seit 1970)."""
    return int(ts.timestamp() * 1_000_000)


def from_id(i: int) -> datetime:
    return datetime.fromtimestamp(i / 1_000_000, UTC)


def _hour_key(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:00:00Z")


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def entry_from(fields: dict[str, Any], ts: datetime) -> dict[str, Any]:
    """Felder eines externen Eintrags → Werte wie bei `LogEntry` (fehlende Felder ergänzt)."""
    rules = fields.get("waf_rules") or []
    if isinstance(rules, str):
        try:
            rules = json.loads(rules)
        except ValueError:
            rules = []
    score = fields.get("waf_score")
    return {
        "ts": ts,
        "node": fields.get("node") or "?",
        "host": "" if fields.get("host") in (None, "-") else fields["host"],
        "method": fields.get("method") or "",
        "uri": fields.get("uri") or "",
        "status": int(_num(fields.get("status"))),
        "duration_ms": _num(fields.get("duration_ms")),
        "size": int(_num(fields.get("size"))),
        "ip": fields.get("ip") or "",
        "country": fields.get("country") or None,
        "device": fields.get("device") or None,
        "person": fields.get("person") or None,
        "reason": fields.get("reason") or "ok",
        "waf_rules": [int(r) for r in rules if str(r).isdigit()],
        "waf_msg": fields.get("waf_msg") or None,
        "waf_score": int(_num(score)) if score not in (None, "") else None,
        "user_agent": fields.get("user_agent") or None,
    }


def _assign_ids(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """IDs aus dem Zeitstempel; gleiche Mikrosekunde → nachfolgende um 1 verringert, damit
    jede ID in einer Seite eindeutig ist (absteigende Reihenfolge)."""
    last = None
    for e in entries:
        i = to_id(e["ts"])
        if last is not None and i >= last:
            i = last - 1
        e["id"] = last = i
    return entries


# ---------- Loki (LogQL) ----------


def _q(v: Any) -> str:
    """String für LogQL bzw. LogsQL (JSON-Quoting passt für beide)."""
    return json.dumps(str(v))


class LokiStore:
    kind = "loki"

    def __init__(self, url: str, tenant: str = "", transport: httpx.BaseTransport | None = None):
        self.base = re.sub(r"/loki/api/v1/push/?$", "", url.strip().rstrip("/"))
        self.tenant = tenant
        self.transport = transport

    # --- Abfrage bauen ---

    def _stream(self, sel: Sel) -> str:
        parts = ['job="tesseract"']
        for c in sel.conds:
            if c.field in LABELS and c.op == "eq":
                parts.append(f"{c.field}={_q(c.value)}")
            elif c.field in LABELS and c.op == "in":
                parts.append(f"{c.field}=~{_q('|'.join(re.escape(v) for v in c.value))}")
        return "{" + ", ".join(parts) + "}"

    def _cond(self, c: Cond) -> str:
        f = c.field
        if c.op == "eq":
            return f"{f}={c.value}" if f in NUMERIC else f"{f}={_q(c.value)}"
        if c.op == "ne":
            return f"{f}!={c.value}" if f in NUMERIC else f"{f}!={_q(c.value)}"
        if c.op == "in":
            return f"{f}=~{_q('|'.join(re.escape(str(v)) for v in c.value))}"
        if c.op == "gte":
            return f"{f}>={c.value}"
        if c.op == "lt":
            return f"{f}<{c.value}"
        if c.op == "re":
            return f"{f}=~{_q(c.value)}"
        if c.op == "ire":
            return f"{f}=~{_q('(?i).*' + c.value + '.*')}"
        if c.op == "cidr":
            return f"{f}=ip({_q(c.value)})"
        raise StoreError(f"Bedingung {c.op} geht hier nicht")

    def _pipeline(self, sel: Sel, extra: set[str] = frozenset(), all_fields: bool = False) -> str:
        """Log-Abfrage: Stream-Selektor, Zeilenfilter, JSON-Felder, Feldfilter."""
        out = self._stream(sel)
        for c in sel.conds:
            if c.op == "rule":
                # Regel-ID in der JSON-Liste – als Zeilenfilter, unabhängig vom Parser
                pattern = '"waf_rules":\\[[^\\]]*\\b' + str(c.value) + "\\b"
                out += f" |~ {_q(pattern)}"
        # Regel-Filter laufen über die Zeile; alle anderen Felder aus dem JSON holen
        used = {c.field for c in sel.conds if c.op != "rule"}
        used |= {c.field for g in sel.any_of for c in g}
        needed = (used | set(extra)) - set(LABELS)
        if all_fields:
            out += " | json"
        elif needed:
            out += " | json " + ", ".join(f'{n}="{n}"' for n in sorted(needed))
        for c in sel.conds:
            if c.op == "rule" or (c.field in LABELS and c.op in ("eq", "in")):
                continue
            out += " | " + self._cond(c)
        for group in sel.any_of:
            out += " | " + " or ".join(self._cond(c) for c in group)
        return out

    # --- HTTP ---

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = {"X-Scope-OrgID": self.tenant} if self.tenant else {}
        try:
            with httpx.Client(transport=self.transport, timeout=60.0) as c:
                r = c.get(self.base + path, params=params, headers=headers)
        except httpx.HTTPError as e:
            raise StoreError(f"Loki nicht erreichbar: {e}") from e
        if r.status_code >= 300:
            raise StoreError(f"Loki antwortet {r.status_code}: {r.text[:300]}")
        data = r.json()
        if data.get("status") != "success":
            raise StoreError(f"Loki: {data.get('error') or data}")
        return data["data"]

    @staticmethod
    def _ns(t: datetime) -> str:
        return str(int(t.timestamp() * 1_000_000_000))

    # --- Einträge ---

    def entries(self, sel: Sel, start: datetime, end: datetime, limit: int, newest_first=True):
        data = self._get(
            "/loki/api/v1/query_range",
            {
                "query": self._pipeline(sel),
                "start": self._ns(start),
                "end": self._ns(end),
                "limit": limit,
                "direction": "backward" if newest_first else "forward",
            },
        )
        out = []
        for stream in data.get("result", []):
            labels = stream.get("stream", {})
            for ns, line in stream.get("values", []):
                try:
                    fields = json.loads(line)
                except ValueError:
                    continue
                fields.update({k: labels.get(k) for k in LABELS})
                ts = datetime.fromtimestamp(int(ns) / 1_000_000_000, UTC)
                out.append(entry_from(fields, ts))
        out.sort(key=lambda e: e["ts"], reverse=newest_first)
        return _assign_ids(out[:limit])

    # --- Aggregate ---

    def _metric(self, inner: str, start: datetime, end: datetime, step: timedelta | None):
        span = (end - start) if step is None else step
        rng = f"{int(span.total_seconds())}s"
        q = inner.replace("$RANGE", rng)
        if step is None:
            data = self._get("/loki/api/v1/query", {"query": q, "time": self._ns(end)})
            return [(r["metric"], [(end, float(r["value"][1]))]) for r in data.get("result", [])]
        # an Stunden ausrichten, damit die Buckets denen aus SQLite entsprechen
        s0 = start.replace(minute=0, second=0, microsecond=0)
        n = -(-(end - s0) // step)  # aufrunden
        data = self._get(
            "/loki/api/v1/query_range",
            {
                "query": q,
                "start": self._ns(s0 + step),
                "end": self._ns(s0 + n * step),
                "step": f"{int(step.total_seconds())}s",
            },
        )
        return [
            (
                r["metric"],
                # Wert bei t zählt (t - step, t] → Beginn des Buckets
                [(datetime.fromtimestamp(float(t), UTC) - step, float(v)) for t, v in r["values"]],
            )
            for r in data.get("result", [])
        ]

    def _group(self, by: list[str]) -> str:
        return f" by ({', '.join(by)})" if by else ""

    def count(self, sel: Sel, start, end, by: list[str] = (), step: timedelta | None = None):
        """[(Werte der Gruppenfelder, Bucket-Beginn oder None, Anzahl)]"""
        by = list(by)
        inner = f"sum{self._group(by)} (count_over_time({self._pipeline(sel, set(by))} [$RANGE]))"
        return self._flatten(self._metric(inner, start, end, step), by, step)

    def total(self, sel: Sel, start, end, fld: str, by: list[str] = ()):
        by = list(by)
        pipe = self._pipeline(sel, {fld, *by}) + f" | unwrap {fld}"
        inner = f"sum{self._group(by)} (sum_over_time({pipe} [$RANGE]))"
        return self._flatten(self._metric(inner, start, end, None), by, None)

    def quantile(self, q: float, sel: Sel, start, end, fld: str, by: list[str] = ()):
        by = list(by)
        pipe = self._pipeline(sel, {fld, *by}) + f" | unwrap {fld}"
        inner = f"quantile_over_time({q}, {pipe} [$RANGE]){self._group(by)}"
        return self._flatten(self._metric(inner, start, end, None), by, None)

    @staticmethod
    def _flatten(series, by, step):
        out = []
        for metric, points in series:
            key = tuple(metric.get(b, "") for b in by)
            for t, v in points:
                if v:
                    out.append((key, t if step else None, v))
        return out


# ---------- VictoriaLogs (LogsQL) ----------


class VictoriaLogsStore:
    kind = "victorialogs"

    def __init__(self, url: str, tenant: str = "", transport: httpx.BaseTransport | None = None):
        self.base = re.sub(r"/insert/jsonline/?$", "", url.strip().rstrip("/"))
        self.tenant = tenant
        self.transport = transport

    def _cond(self, c: Cond) -> str:
        f = c.field
        if c.op == "eq":
            return f"{f}:={_q(c.value)}"
        if c.op == "ne":
            return f"-{f}:={_q(c.value)}"
        if c.op == "in":
            return f"{f}:in({', '.join(_q(v) for v in c.value)})"
        if c.op == "gte":
            return f"{f}:>={c.value}"
        if c.op == "lt":
            return f"{f}:<{c.value}"
        if c.op == "re":
            return f"{f}:~{_q('^(' + c.value + ')$')}"
        if c.op == "ire":
            return f"{f}:~{_q('(?i)' + c.value)}"
        if c.op == "cidr":
            if ":" in c.value:
                raise StoreError("IPv6-Netze gehen mit VictoriaLogs nicht – einzelne IP angeben")
            return f"{f}:ipv4_range({_q(c.value)})"
        if c.op == "rule":
            return f"{f}:~{_q(r'\b' + str(c.value) + r'\b')}"
        raise StoreError(f"Bedingung {c.op} geht hier nicht")

    def _filter(self, sel: Sel, start: datetime, end: datetime) -> str:
        t0 = start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        t1 = end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        parts = [f"_time:[{t0}, {t1})", '{job="tesseract"}']
        parts += [self._cond(c) for c in sel.conds]
        parts += ["(" + " or ".join(self._cond(c) for c in g) + ")" for g in sel.any_of]
        return " ".join(parts)

    def _query(self, query: str, limit: int | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"query": query}
        if limit:
            params["limit"] = limit
        try:
            with httpx.Client(transport=self.transport, timeout=60.0) as c:
                r = c.post(
                    self.base + "/select/logsql/query",
                    data=params,
                    headers=_vl_headers(self.tenant),
                )
        except httpx.HTTPError as e:
            raise StoreError(f"VictoriaLogs nicht erreichbar: {e}") from e
        if r.status_code >= 300:
            raise StoreError(f"VictoriaLogs antwortet {r.status_code}: {r.text[:300]}")
        rows = []
        for line in r.text.splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
        return rows

    @staticmethod
    def _time(v: str) -> datetime:
        # RFC 3339 mit bis zu 9 Nachkommastellen – Python kann nur 6
        m = re.match(r"(.*T\d\d:\d\d:\d\d)(?:\.(\d+))?(Z|[+-]\d\d:\d\d)$", v)
        if not m:
            return datetime.now(UTC)
        frac = (m.group(2) or "0")[:6].ljust(6, "0")
        tz = "+00:00" if m.group(3) == "Z" else m.group(3)
        return datetime.fromisoformat(f"{m.group(1)}.{frac}{tz}").astimezone(UTC)

    def entries(self, sel: Sel, start: datetime, end: datetime, limit: int, newest_first=True):
        order = "desc" if newest_first else "asc"
        q = f"{self._filter(sel, start, end)} | sort by (_time {order}) | limit {limit}"
        rows = self._query(q)
        out = [entry_from(r, self._time(r.get("_time", ""))) for r in rows]
        out.sort(key=lambda e: e["ts"], reverse=newest_first)
        return _assign_ids(out[:limit])

    def _stats(self, sel, start, end, by, func, step=None):
        groups = list(by)
        if step is not None:
            groups.insert(0, f"_time:{int(step.total_seconds())}s")
        q = f"{self._filter(sel, start, end)} | stats"
        if groups:
            q += f" by ({', '.join(groups)})"
        q += f" {func} as v"
        out = []
        for r in self._query(q):
            v = _num(r.get("v"))
            if not v:
                continue
            key = tuple(r.get(b, "") for b in by)
            out.append((key, self._time(r["_time"]) if step is not None else None, v))
        return out

    def count(self, sel: Sel, start, end, by: list[str] = (), step: timedelta | None = None):
        return self._stats(sel, start, end, by, "count()", step)

    def total(self, sel: Sel, start, end, fld: str, by: list[str] = ()):
        return self._stats(sel, start, end, by, f"sum({fld})")

    def quantile(self, q: float, sel: Sel, start, end, fld: str, by: list[str] = ()):
        return self._stats(sel, start, end, by, f"quantile({q}, {fld})")


def store_for(g: dict[str, Any], transport=None) -> "LokiStore | VictoriaLogsStore | None":
    """Externer Speicher, wenn eingeschaltet und eine URL gesetzt ist."""
    if not g.get("logs_external") or not g.get("loki_url"):
        return None
    cls = VictoriaLogsStore if g.get("loki_kind") == "victorialogs" else LokiStore
    return cls(g["loki_url"], g.get("loki_tenant") or "", transport)
