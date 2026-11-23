"""Phase 5: Zentrale Log-Sammlung.

Caddy schreibt pro Node zwei Dateien:
- Zugriffs-Log (`tesseract_access`): eine JSON-Zeile pro Anfrage. Gesperrte Anfragen tragen
  `tesseract_reason` (ip, ban, mtls, internal, websocket, authelia), siehe `caddy/config.py`.
- WAF-Log: pro ausgelöster Regel eine Zeile „Coraza: Warning. … [id "942100"] … [unique_id …]“
  und bei einer Blockade zusätzlich „WAF rule violation detected“ mit derselben unique_id.

Den lokalen Node liest der Controller selbst, die anderen liefern ihre Agents (gepuffert). Die
WAF-Zeilen einer Anfrage werden über Client-IP und URI (± wenige Sekunden) dem Eintrag im
Zugriffs-Log zugeordnet – Coraza schreibt seine Zeilen vor dem Zugriffs-Log.
"""

import ipaddress
import json
import logging
import re
import shlex
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, String, cast, delete, or_, select
from sqlalchemy.orm import Session

from tesseract.db.models import Device, LogEntry, Node, utcnow

log = logging.getLogger("tesseract.logs")

VIOLATION = "WAF rule violation detected"
# Sammelregeln des CRS (Score-Auswertung) – keine sinnvollen Ausnahmen
CRS_SCORE_RULES = {949110, 949111, 959100, 980130, 980140, 980170}
REASONS = ("ok", "waf", "ip", "ban", "mtls", "internal", "websocket", "authelia")
_FIELD_RE = re.compile(r'\[(\w+) "((?:[^"\\]|\\.)*)"\]')
_CLIENT_RE = re.compile(r'^\[client "([^"]+)"\]')
_SCORE_RE = re.compile(r"Total Score: (\d+)")
# WAF-Zeilen so lange vorhalten, bis der passende Zugriffs-Eintrag kommt
PENDING_SECONDS = 60.0
MATCH_SECONDS = 5.0


# ---------- WAF ----------


@dataclass
class WafEvent:
    ts: float
    ip: str
    uri: str
    rules: list[int] = field(default_factory=list)
    msgs: list[str] = field(default_factory=list)
    score: int | None = None
    blocked: bool = False
    host: str = ""
    # Eingang beim Controller (monotonic) – nachgelieferte Logs haben alte Zeitstempel
    added: float = field(default_factory=time.monotonic)


def _ts(entry: dict[str, Any]) -> float:
    try:
        return float(entry.get("ts") or time.time())
    except (TypeError, ValueError):
        return time.time()


class WafTracker:
    """Sammelt die WAF-Zeilen eines Nodes, gruppiert nach Coraza-unique_id."""

    def __init__(self) -> None:
        self.events: dict[str, WafEvent] = {}

    def feed(self, lines: list[str]) -> list[tuple[str, str]]:
        """Verarbeitet WAF-Zeilen. Gibt Blockaden als (ip, host) für die Auto-Sperre zurück."""
        violations = []
        for line in lines:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            msg = str(entry.get("msg") or "")
            if msg == VIOLATION:
                uid = str(entry.get("unique_id") or "")
                ip = str(entry.get("client_ip") or "")
                host = str(entry.get("hostname") or "")
                ev = self.events.setdefault(
                    uid or f"v{len(self.events)}",
                    WafEvent(ts=_ts(entry), ip=ip, uri=str(entry.get("uri") or "")),
                )
                ev.blocked, ev.host = True, host
                if _valid_ip(ip):
                    violations.append((ip, host))
                continue
            if "Coraza:" not in msg:
                continue
            fields = dict(_FIELD_RE.findall(msg))
            uid = fields.get("unique_id", "")
            client = _CLIENT_RE.match(msg)
            ev = self.events.setdefault(
                uid,
                WafEvent(
                    ts=_ts(entry),
                    ip=client.group(1) if client else "",
                    uri=fields.get("uri", ""),
                ),
            )
            try:
                rule = int(fields.get("id", ""))
            except ValueError:
                continue
            if rule in CRS_SCORE_RULES:
                score = _SCORE_RE.search(fields.get("msg", "") + " " + fields.get("data", ""))
                if score:
                    ev.score = int(score.group(1))
                continue
            if rule not in ev.rules:
                ev.rules.append(rule)
                ev.msgs.append(fields.get("msg", "")[:200])
        self._prune()
        return violations

    def _prune(self) -> None:
        cutoff = time.monotonic() - PENDING_SECONDS
        for uid in [u for u, e in self.events.items() if e.added < cutoff]:
            del self.events[uid]

    def take(self, ip: str, uri: str, ts: float) -> WafEvent | None:
        """WAF-Ereignis zu einer Anfrage holen (und vergessen). Erst über IP + URI, sonst nur
        über die URI (hinter Proxys sieht Coraza evtl. eine andere IP als das Zugriffs-Log)."""
        near = [
            (uid, ev)
            for uid, ev in self.events.items()
            if ev.uri == uri and abs(ev.ts - ts) <= MATCH_SECONDS
        ]
        hit = next(((u, e) for u, e in near if e.ip == ip), near[0] if near else None)
        if hit is None:
            return None
        del self.events[hit[0]]
        return hit[1]


def _valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return False
    return True


# ---------- GeoIP (optional) ----------


class Geo:
    """Land zu einer IP aus einer lokalen MaxMind-/DB-IP-Datenbank (.mmdb)."""

    def __init__(self, path: Any = None) -> None:
        self.reader = None
        if path:
            try:
                import maxminddb

                self.reader = maxminddb.open_database(str(path))
            except (OSError, ValueError) as e:
                log.warning("GeoIP-Datenbank %s nicht lesbar: %s", path, e)

    @property
    def ready(self) -> bool:
        return self.reader is not None

    def country(self, ip: str) -> str | None:
        if self.reader is None:
            return None
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return None
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return None
        try:
            rec = self.reader.get(ip)
        except ValueError:
            return None
        if not isinstance(rec, dict):
            return None
        code = (rec.get("country") or rec.get("registered_country") or {}).get("iso_code")
        return str(code)[:2] if code else None


# ---------- Zugriffs-Log ----------


def _header(headers: dict[str, Any], name: str) -> str:
    for k, v in (headers or {}).items():
        if k.lower() == name.lower():
            return str(v[0] if isinstance(v, list) and v else v)
    return ""


def _proto(raw: str) -> str | None:
    v = raw.upper().removeprefix("HTTP/")
    return {"1.0": "1.0", "1.1": "1.1", "2": "2", "2.0": "2", "3": "3", "3.0": "3"}.get(v)


def parse_access(line: str) -> dict[str, Any] | None:
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    if not isinstance(entry, dict) or entry.get("msg") != "handled request":
        return None
    req = entry.get("request") or {}
    ip = str(req.get("client_ip") or req.get("remote_ip") or "")
    if not _valid_ip(ip):
        return None
    tls = req.get("tls") or {}
    host = str(req.get("host") or "").lower()
    host = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    return {
        "ts": _ts(entry),
        "host": host[:253],
        "method": str(req.get("method") or "")[:16],
        "uri": str(req.get("uri") or "")[:2048],
        "status": int(entry.get("status") or 0),
        "duration_ms": round(float(entry.get("duration") or 0) * 1000, 3),
        "size": int(entry.get("size") or 0),
        "bytes_in": int(entry.get("bytes_read") or 0),
        # HTTP/1.1 | HTTP/2.0 | HTTP/3.0 → 1.1 | 2 | 3
        "proto": _proto(str(req.get("proto") or "")),
        "encoding": _header(entry.get("resp_headers") or {}, "Content-Encoding")[:16] or None,
        "ip": ip,
        "reason": str(entry.get("tesseract_reason") or "ok")[:16],
        "user_agent": _header(req.get("headers") or {}, "User-Agent")[:255] or None,
        "client_serial": str(tls.get("client_serial") or ""),
    }


def _serial_hex(serial: str) -> str:
    """Caddy schreibt die Seriennummer dezimal, gespeichert ist sie hex."""
    try:
        return format(int(serial), "x")
    except ValueError:
        return serial.lower()


@dataclass
class IngestResult:
    entries: int = 0
    violations: list[tuple[str, str]] = field(default_factory=list)


def ingest(
    db: Session,
    node: Node,
    access_lines: list[str],
    waf_lines: list[str],
    tracker: WafTracker,
    geo: Geo | None = None,
    metrics=None,
    sink=None,
) -> IngestResult:
    """Speichert neue Zeilen eines Nodes. Commit macht der Aufrufer."""
    result = IngestResult(violations=tracker.feed(waf_lines))
    parsed = [p for line in access_lines if (p := parse_access(line))]
    if not parsed:
        return result
    serials = {_serial_hex(p["client_serial"]) for p in parsed if p["client_serial"]}
    devices = (
        {d.serial: d for d in db.scalars(select(Device).where(Device.serial.in_(serials)))}
        if serials
        else {}
    )
    seen: dict[int, datetime] = {}
    for p in parsed:
        ev = tracker.take(p["ip"], p["uri"], p["ts"])
        reason = p["reason"]
        if ev and ev.blocked and reason == "ok" and p["status"] in (403, 0):
            reason = "waf"
        device = devices.get(_serial_hex(p["client_serial"])) if p["client_serial"] else None
        ts = datetime.fromtimestamp(p["ts"], UTC)
        db.add(
            LogEntry(
                ts=ts,
                node_id=node.id,
                host=p["host"],
                method=p["method"],
                uri=p["uri"],
                status=p["status"],
                duration_ms=p["duration_ms"],
                size=p["size"],
                bytes_in=p["bytes_in"],
                proto=p["proto"],
                encoding=p["encoding"],
                ip=p["ip"],
                country=geo.country(p["ip"]) if geo else None,
                device_id=device.id if device else None,
                reason=reason if reason in REASONS else "ok",
                waf_rules=ev.rules if ev else [],
                waf_msg=(ev.msgs[0] if ev and ev.msgs else None),
                waf_score=ev.score if ev else None,
                user_agent=p["user_agent"],
            )
        )
        if sink is not None:
            sink(
                {
                    "ts": ts,
                    "node": node.name,
                    "host": p["host"],
                    "reason": reason if reason in REASONS else "ok",
                    "method": p["method"],
                    "uri": p["uri"],
                    "status": p["status"],
                    "duration_ms": p["duration_ms"],
                    "size": p["size"],
                    "bytes_in": p["bytes_in"],
                    "proto": p["proto"],
                    "encoding": p["encoding"],
                    "ip": p["ip"],
                    "country": geo.country(p["ip"]) if geo else None,
                    "device": device.name if device else None,
                    "person": device.person.name if device else None,
                    "waf_rules": ev.rules if ev else [],
                    "waf_msg": ev.msgs[0] if ev and ev.msgs else None,
                    "waf_score": ev.score if ev else None,
                    "user_agent": p["user_agent"],
                }
            )
        if metrics is not None:
            metrics.observe(node.name, p["host"], p["status"], reason, p["duration_ms"], p["size"])
        if device is not None:
            seen[device.id] = max(seen.get(device.id, ts), ts)
        result.entries += 1
    # „zuletzt gesehen“ der Geräte
    for dev_id, ts in seen.items():
        d = db.get(Device, dev_id)
        if d is not None and (d.last_seen_at is None or d.last_seen_at < ts):
            d.last_seen_at = ts
    return result


def prune(db: Session, days: int) -> int:
    cutoff = utcnow() - timedelta(days=max(1, int(days)))
    res = db.execute(delete(LogEntry).where(LogEntry.ts < cutoff))
    return res.rowcount or 0


# ---------- Suche ----------

FILTERS = {
    "all": None,
    "denied": "denied",
    "mtls": ["mtls"],
    "waf": ["waf"],
    "ip": ["ip", "ban", "internal"],
}
SEARCH_KEYS = ("host", "node", "status", "ip", "reason", "rule", "method", "device", "country")


class QueryError(ValueError):
    pass


def apply_query(stmt: Select, q: str) -> Select:
    """Filtersyntax: `host:git status:403 ip:198.51.100.7 reason:waf rule:942100 node:pi`
    plus freier Text (Teil der URI oder des Hosts). `status:4xx` für ganze Klassen."""
    try:
        tokens = shlex.split(q or "")
    except ValueError as e:
        raise QueryError("Anführungszeichen nicht geschlossen") from e
    for tok in tokens:
        key, sep, value = tok.partition(":")
        key = key.lower()
        if not sep or key not in SEARCH_KEYS:
            like = f"%{tok}%"
            stmt = stmt.where(or_(LogEntry.uri.ilike(like), LogEntry.host.ilike(like)))
            continue
        if not value:
            raise QueryError(f"„{key}:“ ohne Wert")
        if key == "host":
            stmt = stmt.where(
                or_(LogEntry.host == value.lower(), LogEntry.host.like(f"{value.lower()}.%"))
            )
        elif key == "node":
            stmt = stmt.where(LogEntry.node_id.in_(select(Node.id).where(Node.name == value)))
        elif key == "status":
            v = value.lower()
            if re.fullmatch(r"[1-5]xx", v):
                base = int(v[0]) * 100
                stmt = stmt.where(LogEntry.status >= base, LogEntry.status < base + 100)
            elif v.isdigit():
                stmt = stmt.where(LogEntry.status == int(v))
            else:
                raise QueryError("status: Zahl oder z. B. 4xx")
        elif key == "ip":
            if "/" in value:
                try:
                    net = ipaddress.ip_network(value, strict=False)
                except ValueError as e:
                    raise QueryError(f"ip: {value} ist kein Netz") from e
                # Netze: grob über das Präfix (SQLite kennt keine IP-Typen)
                prefix = str(net.network_address).rstrip("0").rstrip(".:")
                stmt = stmt.where(LogEntry.ip.like(f"{prefix}%"))
            else:
                stmt = stmt.where(LogEntry.ip == value)
        elif key == "reason":
            stmt = stmt.where(LogEntry.reason == value.lower())
        elif key == "rule":
            if not value.isdigit():
                raise QueryError("rule: Regel-ID als Zahl")
            # JSON-Liste, z. B. "[942100, 920350]"
            stmt = stmt.where(
                or_(
                    *(
                        cast(LogEntry.waf_rules, String).like(p)
                        for p in (f"[{value}]", f"[{value},%", f"%, {value},%", f"%, {value}]")
                    )
                )
            )
        elif key == "method":
            stmt = stmt.where(LogEntry.method == value.upper())
        elif key == "country":
            stmt = stmt.where(LogEntry.country == value.upper())
        elif key == "device":
            ids = select(Device.id).where(Device.name.ilike(f"%{value}%"))
            stmt = stmt.where(LogEntry.device_id.in_(ids))
    return stmt


def apply_filter(stmt: Select, name: str) -> Select:
    f = FILTERS.get(name)
    if f is None:
        return stmt
    if f == "denied":
        return stmt.where(or_(LogEntry.reason != "ok", LogEntry.status >= 400))
    return stmt.where(LogEntry.reason.in_(f))


class Collector:
    """Hält pro Node den WAF-Zwischenstand und die GeoIP-Datenbank (eine Instanz pro App)."""

    def __init__(self, geo: Geo | None = None) -> None:
        from tesseract.loki import LokiShipper
        from tesseract.metrics import Metrics

        self.geo = geo or Geo()
        self.trackers: dict[int, WafTracker] = {}
        self.metrics = Metrics()
        # zusätzlicher Speicher in Loki (optional)
        self.loki = LokiShipper()

    def node(
        self, db: Session, node: Node, access_lines: list[str], waf_lines: list[str]
    ) -> list[tuple[str, str]]:
        tracker = self.trackers.setdefault(node.id, WafTracker())
        return ingest(
            db, node, access_lines, waf_lines, tracker, self.geo, self.metrics, self.loki.add
        ).violations

    def local(
        self, db: Session, access_lines: list[str], waf_lines: list[str]
    ) -> list[tuple[str, str]]:
        """Zeilen des lokalen Caddy (Node `local`)."""
        node = db.scalar(select(Node).where(Node.kind == "local").order_by(Node.id))
        if node is None:
            return WafTracker().feed(waf_lines)
        return self.node(db, node, access_lines, waf_lines)

    def prune(self, db: Session) -> int:
        from tesseract.services import get_general

        return prune(db, int(get_general(db)["logs_days"]))
