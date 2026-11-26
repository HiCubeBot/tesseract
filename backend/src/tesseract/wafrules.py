"""WAF-Regeln (OWASP CRS) nachschlagen und Ausnahmen gezielt setzen.

- **Katalog:** `data/crs_catalog.json`, erzeugt aus den CRS-Dateien der coraza-caddy-Version im
  Caddy-Image (`backend/scripts/crs_catalog.py`, läuft beim Image-Build).
- **Treffer:** aus der eigenen Log-Datenbank (`LogEntry.waf_rules`), je Regel für 24 h / 7 / 30
  Tage, mit Hosts, Pfaden und betroffenen Feldern.
- **Ausnahmen:** `WafException` – ganz (wie `Host.waf_exclusions`, nur mit Kommentar und Ablauf)
  oder gezielt für ein Feld (`ARGS:q`, `REQUEST_HEADERS:User-Agent`, `REQUEST_COOKIES:sid` …)
  und/oder einen Pfad. Gezielte Ausnahmen werden zu einer eigenen Regel mit
  `ctl:ruleRemoveTargetById` bzw. `ctl:ruleRemoveById` vor dem CRS – nie freier SecLang-Text:
  Ziel und Pfad sind streng geprüft, eine unbekannte Regel-ID bleibt folgenlos.
- **Ablauf:** abgelaufene Ausnahmen entfernt `expire()` (Audit-Eintrag, Host-Version, Übertragen).
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.db.models import Host, LogEntry, WafException, utcnow

CATALOG = Path(__file__).parent / "data" / "crs_catalog.json"
# Regeln, die nur den Anomalie-Score auswerten – keine eigenen Treffer
SCORE_RULES = range(949000, 950000), range(959000, 960000), range(980000, 981000)
# Eigene Regel-IDs für gezielte Ausnahmen: weit weg vom CRS (9xxxxx) und von eigenen Regeln
EXCEPTION_RULE_BASE = 10_000_000

# Felder, die eine gezielte Ausnahme betreffen darf; Name ohne Anführungszeichen, Kommas,
# Semikolons, Leerzeichen oder Backslash (landet in einer Coraza-Aktion)
TARGET_RE = re.compile(
    r"^(ARGS|ARGS_GET|ARGS_POST|ARGS_NAMES|ARGS_GET_NAMES|ARGS_POST_NAMES|REQUEST_HEADERS|"
    r"REQUEST_HEADERS_NAMES|REQUEST_COOKIES|REQUEST_COOKIES_NAMES|FILES|FILES_NAMES|XML|JSON|"
    r"REQUEST_BODY|REQUEST_URI|REQUEST_FILENAME|REQUEST_BASENAME|QUERY_STRING)"
    r"(:[A-Za-z0-9_.\-\[\]@/]{1,128})?$"
)
PATH_RE = re.compile(r"^/[A-Za-z0-9/_\-.~%@+]{0,250}$")
WINDOWS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}


# ---------- Katalog ----------


@lru_cache(maxsize=1)
def catalog() -> dict[str, Any]:
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"crs": "", "coraza_caddy": "", "rules": []}


def rules_by_id() -> dict[int, dict[str, Any]]:
    return {r["id"]: r for r in catalog()["rules"]}


def is_score_rule(rule_id: int) -> bool:
    return any(rule_id in r for r in SCORE_RULES)


# ---------- Eingaben prüfen ----------


def clean_target(value: str) -> str:
    v = value.strip()
    if not v:
        return ""
    if not TARGET_RE.match(v):
        raise ValueError(
            "Ziel wie ARGS:name, REQUEST_HEADERS:User-Agent oder REQUEST_COOKIES:sid angeben"
        )
    return v


def clean_path(value: str) -> str:
    v = value.strip()
    if not v:
        return ""
    if not v.startswith("/"):
        v = "/" + v
    if not PATH_RE.match(v):
        raise ValueError("Pfad wie /api/upload – ohne Leerzeichen, Anführungszeichen oder Query")
    return v


# ---------- Coraza-Direktiven ----------


def exception_directives(items: list[tuple[int, int, str, str]]) -> list[str]:
    """Gezielte Ausnahmen (id, rule, target, path) → Regeln, die *vor* dem CRS stehen müssen.

    - nur Ziel:       SecAction … ctl:ruleRemoveTargetById=RULE;TARGET
    - nur Pfad:       SecRule REQUEST_FILENAME "@beginsWith PATH" … ctl:ruleRemoveById=RULE
    - Ziel und Pfad:  SecRule REQUEST_FILENAME "@beginsWith PATH" … ctl:ruleRemoveTargetById=…
    Ganze Ausnahmen ohne Ziel und Pfad laufen weiter über SecRuleRemoveById (waf_exclusions)."""
    out = []
    for exc_id, rule, target, path in sorted(items):
        if not target and not path:
            continue
        rid = EXCEPTION_RULE_BASE + int(exc_id)
        ctl = (
            f"ctl:ruleRemoveTargetById={int(rule)};{target}"
            if target
            else f"ctl:ruleRemoveById={int(rule)}"
        )
        actions = f"id:{rid},phase:1,pass,nolog,{ctl}"
        if path:
            out.append(f'SecRule REQUEST_FILENAME "@beginsWith {path}" "{actions}"')
        else:
            out.append(f'SecAction "{actions}"')
    return out


def host_exceptions(db: Session, host_id: int) -> list[tuple[int, int, str, str]]:
    """Aktive gezielte Ausnahmen eines Hosts für die Caddy-Config."""
    now = utcnow()
    return [
        (e.id, e.rule_id, e.target, e.path)
        for e in db.scalars(select(WafException).where(WafException.host_id == host_id))
        if (e.target or e.path) and (e.expires_at is None or e.expires_at > now)
    ]


# ---------- Treffer ----------


def _path(uri: str) -> str:
    return urlsplit(uri or "/").path or "/"


def hits(db: Session, now: datetime | None = None) -> dict[int, dict[str, int]]:
    """Treffer je Regel in den Fenstern 24h / 7d / 30d (ohne Score-Regeln)."""
    now = now or utcnow()
    since = now - WINDOWS["30d"]
    out: dict[int, dict[str, int]] = defaultdict(lambda: dict.fromkeys(WINDOWS, 0))
    rows = db.execute(
        select(LogEntry.ts, LogEntry.waf_rules)
        .where(LogEntry.ts >= since)
        .where(LogEntry.waf_rules.is_not(None))
    )
    for ts, rules in rows:
        for r in rules or []:
            if is_score_rule(r):
                continue
            for name, span in WINDOWS.items():
                if ts >= now - span:
                    out[r][name] += 1
    return dict(out)


def rule_detail(db: Session, rule_id: int, now: datetime | None = None) -> dict[str, Any]:
    """Treffer einer Regel: Fenster, häufigste Hosts, Pfade und Felder (30 Tage)."""
    now = now or utcnow()
    since = now - WINDOWS["30d"]
    counts = dict.fromkeys(WINDOWS, 0)
    by_host: Counter[str] = Counter()
    by_path: Counter[tuple[str, str]] = Counter()
    by_target: Counter[str] = Counter()
    last: datetime | None = None
    rows = db.execute(
        select(LogEntry.ts, LogEntry.host, LogEntry.uri, LogEntry.waf_rules, LogEntry.waf_targets)
        .where(LogEntry.ts >= since)
        .where(LogEntry.waf_rules.is_not(None))
    )
    for ts, host, uri, rules, targets in rows:
        if rule_id not in (rules or []):
            continue
        for name, span in WINDOWS.items():
            if ts >= now - span:
                counts[name] += 1
        by_host[host] += 1
        by_path[(host, _path(uri))] += 1
        t = (targets or {}).get(str(rule_id))
        if t:
            by_target[t] += 1
        last = ts if last is None or ts > last else last
    return {
        "hits": counts,
        "last_hit": last,
        "hosts": [{"host": h, "count": n} for h, n in by_host.most_common(20)],
        "paths": [{"host": h, "path": p, "count": n} for (h, p), n in by_path.most_common(20)],
        "targets": [{"target": t, "count": n} for t, n in by_target.most_common(10)],
    }


def hits_since(db: Session, host: str, rule_id: int, since: datetime) -> int:
    """Treffer einer Regel auf einem Host seit einem Zeitpunkt (für gezielte Ausnahmen)."""
    n = 0
    rows = db.execute(
        select(LogEntry.waf_rules)
        .where(LogEntry.ts >= since)
        .where(LogEntry.host == host)
        .where(LogEntry.waf_rules.is_not(None))
    )
    for (rules,) in rows:
        if rule_id in (rules or []):
            n += 1
    return n


# ---------- Ablauf ----------


def expired(db: Session, now: datetime | None = None) -> list[WafException]:
    now = now or utcnow()
    return list(
        db.scalars(
            select(WafException).where(
                WafException.expires_at.is_not(None), WafException.expires_at <= now
            )
        )
    )


def expire(db: Session, settings, transport=None, now: datetime | None = None) -> int:
    """Abgelaufene Ausnahmen entfernen: ganze Ausnahmen auch aus `waf_exclusions` (neue
    Host-Version), Audit-Eintrag, Config an die betroffenen Nodes. Gibt die Anzahl zurück."""
    from tesseract import audit
    from tesseract.services import add_version, apply_node, diff, snapshot

    items = expired(db, now)
    if not items:
        return 0
    nodes = set()
    for e in items:
        host: Host | None = db.get(Host, e.host_id)
        if host is None:
            db.delete(e)
            continue
        if not e.target and not e.path and e.rule_id in (host.waf_exclusions or []):
            before = snapshot(host)
            host.waf_exclusions = [r for r in host.waf_exclusions if r != e.rule_id]
            db.flush()
            host.version += 1
            add_version(db, host, actor="system", comment=f"WAF-Ausnahme {e.rule_id} abgelaufen")
            audit.record(
                db,
                actor="system",
                action="host_updated",
                target=host.domain,
                details={"version": host.version, "changes": diff(before, snapshot(host))},
            )
        audit.record(
            db,
            actor="system",
            action="waf_exception_expired",
            target=host.domain,
            details=describe(e),
        )
        nodes.add(host.node_id)
        db.delete(e)
    db.commit()
    from tesseract.db.models import Node

    for node_id in nodes:
        node = db.get(Node, node_id)
        if node is not None:
            apply_node(db, node, settings, transport)
    db.commit()
    return len(items)


def describe(e: WafException) -> dict[str, Any]:
    return {
        "rule": e.rule_id,
        "target": e.target or None,
        "path": e.path or None,
        "comment": e.comment or None,
        "expires_at": e.expires_at.isoformat() if e.expires_at else None,
    }


async def watch(app, interval: float = 600.0) -> None:
    """Alle 10 Minuten abgelaufene Ausnahmen entfernen."""
    import asyncio
    import logging

    log = logging.getLogger("tesseract.waf")
    while True:
        try:
            with app.state.db.sessionmaker() as db:
                n = await asyncio.to_thread(
                    expire, db, app.state.settings, app.state.caddy_transport
                )
                if n:
                    log.info("%d WAF-Ausnahme(n) abgelaufen und entfernt", n)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover – die Schleife darf nie sterben
            log.exception("WAF-Ausnahmen: Fehler beim Ablauf")
        await asyncio.sleep(interval)
