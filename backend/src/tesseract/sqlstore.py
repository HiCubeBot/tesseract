"""Dieselbe Abfrage-Schnittstelle wie `logstore` (Loki/VictoriaLogs), aber über SQLite.

Damit lassen sich Auswertungen einmal schreiben und laufen mit jedem Speicher:
`count`, `total` und `quantile` liefern `[(Werte der Gruppenfelder, Bucket-Beginn oder None,
Wert)]`. Felder wie in der JSON-Zeile (`node`, `device`, `person` werden über die Namen
aufgelöst).
"""

import ipaddress
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Integer, String, and_, cast, func, not_, or_, select
from sqlalchemy.orm import Session

from tesseract.db.models import Device, LogEntry, Node, Person
from tesseract.logstore import Cond, Sel, StoreError

# Stichprobe für Quantile (wie in `stats.py`)
QUANTILE_SAMPLE = 50_000


class SqlStore:
    kind = "sqlite"

    def __init__(self, db: Session):
        self.db = db

    # --- Felder und Bedingungen ---

    @staticmethod
    def _col(name: str) -> Any:
        if name == "node":
            return Node.name
        if name == "device":
            return Device.name
        if name == "person":
            return Person.name
        col = getattr(LogEntry, name, None)
        if col is None or name in ("id", "ts", "node_id", "device_id"):
            raise StoreError(f"Feld {name} gibt es nicht")
        return col

    def _cond(self, c: Cond) -> Any:
        col = self._col(c.field)
        v = c.value
        if c.op == "eq":
            return col == v
        if c.op == "ne":
            return or_(col != v, col.is_(None))
        if c.op == "in":
            return col.in_(list(v))
        if c.op == "gte":
            return col >= v
        if c.op == "lt":
            return col < v
        text = func.coalesce(cast(col, String), "")
        if c.op == "re":
            return text.regexp_match("^(" + v + ")$")
        if c.op == "ire":
            return text.regexp_match("(?i)" + v)
        if c.op == "nire":
            return not_(text.regexp_match("(?i)" + v))
        if c.op == "cidr":
            net = ipaddress.ip_network(v, strict=False)
            ips = [
                ip for (ip,) in self.db.execute(select(LogEntry.ip).distinct()) if _in_net(ip, net)
            ]
            return LogEntry.ip.in_(ips)
        if c.op == "rule":
            return func.coalesce(cast(LogEntry.waf_rules, String), "").regexp_match(
                r"\b" + str(int(v)) + r"\b"
            )
        raise StoreError(f"Bedingung {c.op} geht hier nicht")

    def _where(self, sel: Sel, start: datetime, end: datetime) -> list[Any]:
        out = [LogEntry.ts >= start, LogEntry.ts < end]
        out += [self._cond(c) for c in sel.conds]
        out += [or_(*(self._cond(c) for c in g)) for g in sel.any_of]
        return out

    def _select(self, sel: Sel, by: list[str], *cols: Any):
        fields = set(by) | sel.fields()
        stmt = select(*(self._col(b) for b in by), *cols).select_from(LogEntry)
        if "node" in fields:
            stmt = stmt.join(Node, Node.id == LogEntry.node_id)
        if fields & {"device", "person"}:
            stmt = stmt.outerjoin(Device, Device.id == LogEntry.device_id)
        if "person" in fields:
            stmt = stmt.outerjoin(Person, Person.id == Device.person_id)
        return stmt

    @staticmethod
    def _bucket(step: timedelta) -> Any:
        s = int(step.total_seconds())
        return cast(func.strftime("%s", LogEntry.ts), Integer) / s * s

    @staticmethod
    def _key(row, n: int) -> tuple[str, ...]:
        return tuple("" if v is None else str(v) for v in row[:n])

    # --- Abfragen ---

    def _agg(self, sel: Sel, start, end, by, agg: Any, step: timedelta | None):
        by = list(by)
        cols = [agg]
        if step is not None:
            cols.insert(0, self._bucket(step))
        stmt = self._select(sel, by, *cols).where(and_(*self._where(sel, start, end)))
        group = [self._col(b) for b in by]
        if step is not None:
            group.append(self._bucket(step))
        if group:
            stmt = stmt.group_by(*group)
        out = []
        for row in self.db.execute(stmt):
            v = row[-1]
            if not v:
                continue
            t = datetime.fromtimestamp(int(row[len(by)]), UTC) if step is not None else None
            out.append((self._key(row, len(by)), t, float(v)))
        return out

    def count(self, sel: Sel, start, end, by: list[str] = (), step: timedelta | None = None):
        return self._agg(sel, start, end, by, func.count(), step)

    def total(self, sel: Sel, start, end, fld: str, by: list[str] = (), step=None):
        return self._agg(sel, start, end, by, func.sum(self._col(fld)), step)

    def quantile(self, q: float, sel: Sel, start, end, fld: str, by: list[str] = (), step=None):
        by = list(by)
        cols = [self._col(fld)]
        if step is not None:
            cols.insert(0, self._bucket(step))
        stmt = (
            self._select(sel, by, *cols)
            .where(and_(*self._where(sel, start, end)))
            .order_by(LogEntry.id.desc())
            .limit(QUANTILE_SAMPLE)
        )
        groups: dict[tuple, list[float]] = defaultdict(list)
        for row in self.db.execute(stmt):
            t = int(row[len(by)]) if step is not None else None
            groups[(self._key(row, len(by)), t)].append(float(row[-1] or 0))
        out = []
        for (key, t), values in groups.items():
            values.sort()
            k = max(0, min(len(values) - 1, round(q * (len(values) - 1))))
            when = datetime.fromtimestamp(t, UTC) if t is not None else None
            out.append((key, when, values[k]))
        return out


def _in_net(ip: str, net) -> bool:
    try:
        return ipaddress.ip_address(ip) in net
    except ValueError:
        return False


# Kennungen von Bots und Crawlern im User-Agent (für „Besucher ohne Bots“ und die Clients)
BOT_PATTERN = (
    r"bot|crawl|spider|slurp|scan|curl|wget|python|go-http|libwww|okhttp|java/|httpclient"
    r"|monitor|uptime|check|prometheus|headless|facebookexternalhit|preview"
)
BOT_RE = re.compile(BOT_PATTERN, re.I)
