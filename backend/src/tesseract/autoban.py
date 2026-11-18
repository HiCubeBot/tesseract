"""Auto-Sperre: liest WAF-Treffer aus Caddys Logdatei und sperrt auffällige IPs.

Caddy schreibt jeden blockierten Angriff als JSON-Zeile
`{"msg": "WAF rule violation detected", "client_ip": …, "hostname": …}` (siehe
`caddy/config.py`, Logger `tesseract_waf`). Diese Klasse liest neue Zeilen, zählt Treffer
pro IP im Zeitfenster und legt bei Überschreitung eine Sperre an.
"""

import asyncio
import ipaddress
import json
import logging
import time
from collections import defaultdict, deque
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract import audit
from tesseract.db import Database
from tesseract.db.models import Ban, utcnow
from tesseract.services import active_bans, apply_all, get_general

log = logging.getLogger("tesseract.autoban")

VIOLATION = "WAF rule violation detected"


class LogTail:
    """Liest eine wachsende Datei weiter; erkennt Rotation (Datei kleiner als zuvor)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset: int | None = None  # None = beim ersten Lesen ans Ende springen

    def read_new(self) -> list[str]:
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            return []
        if self.offset is None:
            self.offset = size
            return []
        if size < self.offset:
            self.offset = 0
        if size == self.offset:
            return []
        with self.path.open("rb") as f:
            f.seek(self.offset)
            data = f.read()
        # nur vollständige Zeilen verarbeiten
        cut = data.rfind(b"\n") + 1
        self.offset += cut
        return data[:cut].decode("utf-8", "replace").splitlines()


def parse_violation(line: str) -> tuple[str, str] | None:
    """Gibt (client_ip, hostname) zurück, wenn die Zeile ein WAF-Treffer ist."""
    try:
        entry: dict[str, Any] = json.loads(line)
    except ValueError:
        return None
    if entry.get("msg") != VIOLATION:
        return None
    ip = str(entry.get("client_ip") or "").strip()
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return None
    return ip, str(entry.get("hostname") or "")


def _exempt(ip: str, networks: list[str]) -> bool:
    addr = ipaddress.ip_address(ip)
    for n in networks:
        try:
            if addr in ipaddress.ip_network(n, strict=False):
                return True
        except ValueError:
            continue
    return False


class AutoBan:
    def __init__(self, clock=time.monotonic) -> None:
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.clock = clock

    def feed(self, db: Session, violations: list[tuple[str, str]]) -> list[Ban]:
        """Zählt Treffer und legt Sperren an. Commit macht der Aufrufer."""
        g = get_general(db)
        if not g["autoban_enabled"] or not violations:
            return []
        window = int(g["autoban_window_minutes"]) * 60
        limit = int(g["autoban_hits"])
        already = set(active_bans(db))
        created: list[Ban] = []
        now = self.clock()
        for ip, host in violations:
            q = self.hits[ip]
            q.append(now)
            while q and q[0] < now - window:
                q.popleft()
            if len(q) < limit or ip in already or _exempt(ip, g["autoban_exempt"]):
                continue
            ban = Ban(
                ip=ip,
                expires_at=utcnow() + timedelta(hours=int(g["autoban_hours"])),
                reason=f"{len(q)} WAF-Treffer in {g['autoban_window_minutes']} Min.",
                hits=len(q),
                host=host,
            )
            db.add(ban)
            audit.record(
                db,
                actor="system",
                action="ip_banned",
                target=ip,
                details={"hits": len(q), "host": host, "hours": g["autoban_hours"]},
            )
            already.add(ip)
            q.clear()
            created.append(ban)
        return created


def expire_bans(db: Session) -> list[Ban]:
    """Abgelaufene Sperren beenden (Commit macht der Aufrufer)."""
    now = utcnow()
    expired = list(db.scalars(select(Ban).where(Ban.lifted_at.is_(None), Ban.expires_at <= now)))
    for b in expired:
        b.lifted_at, b.lifted_by = now, "Ablauf"
    return expired


async def watch(
    database: Database,
    settings,
    transport=None,
    interval: float = 5.0,
    banner: AutoBan | None = None,
    collector=None,
) -> None:
    """Hintergrund-Aufgabe des Controllers: WAF- und Zugriffs-Log des lokalen Caddy lesen.
    `banner` und `collector` teilt sie sich mit den Agents (Phase 4/5)."""
    from tesseract.logs import Collector

    tail = LogTail(settings.waf_log_path) if settings.waf_log_path else None
    access = LogTail(settings.access_log_path) if settings.access_log_path else None
    banner = banner or AutoBan()
    collector = collector or Collector()
    if tail is None:
        log.info("Kein WAF-Log konfiguriert (TESSERACT_WAF_LOG_PATH) – Auto-Sperre ohne Daten")
    if access is None:
        log.info("Kein Zugriffs-Log konfiguriert (TESSERACT_ACCESS_LOG_PATH) – keine Logs")
    rounds = 0
    while True:
        try:
            waf_lines = await asyncio.to_thread(tail.read_new) if tail else []
            access_lines = await asyncio.to_thread(access.read_new) if access else []
            with database.sessionmaker() as db:
                violations = collector.local(db, access_lines, waf_lines)
                changed = banner.feed(db, violations) + expire_bans(db)
                # Aufbewahrung: etwa alle 10 Minuten alte Einträge löschen
                if rounds % 120 == 0:
                    collector.prune(db)
                db.commit()
                if changed:
                    for b in changed:
                        log.warning(
                            "IP %s %s", b.ip, "entsperrt (Ablauf)" if b.lifted_at else "gesperrt"
                        )
                    await asyncio.to_thread(apply_all, db, settings, transport)
                    db.commit()
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover – die Schleife darf nie sterben
            log.exception("Auto-Sperre/Logs: Fehler beim Auswerten")
        rounds += 1
        await asyncio.sleep(interval)
