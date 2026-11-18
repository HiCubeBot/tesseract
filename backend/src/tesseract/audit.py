"""Audit-Log. Phase 5: unveränderlich, Einträge über Prüfsummen verkettet.

Jeder Eintrag bekommt `hash = SHA-256(vorheriger hash + Inhalt)`. Versiegelt wird nachträglich
in Reihenfolge der IDs (`seal`) – so entsteht auch bei gleichzeitigen Schreibern keine
Gabelung. Trigger in der Datenbank verbieten Ändern und Löschen versiegelter Einträge; wer die
Datei direkt manipuliert, fällt bei `verify` auf.
"""

import hashlib
import json
import threading
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.db.models import AuditEntry

GENESIS = "0" * 64
_seal_lock = threading.Lock()


def record(
    db: Session,
    *,
    actor: str,
    action: str,
    target: str = "",
    details: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditEntry:
    """Legt einen Eintrag an. Commit übernimmt der Aufrufer – so landet er in derselben
    Transaktion wie die Änderung selbst."""
    entry = AuditEntry(actor=actor, action=action, target=target, details=details or {}, ip=ip)
    db.add(entry)
    return entry


def entry_hash(prev: str, e: AuditEntry) -> str:
    content = [
        prev,
        e.id,
        e.created_at.isoformat(timespec="microseconds"),
        e.actor,
        e.action,
        e.target,
        e.details or {},
        e.ip,
    ]
    raw = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def seal(db: Session) -> int:
    """Versiegelt alle noch offenen Einträge (in ID-Reihenfolge) und committet."""
    with _seal_lock:
        last = db.scalar(
            select(AuditEntry.hash)
            .where(AuditEntry.hash.is_not(None))
            .order_by(AuditEntry.id.desc())
            .limit(1)
        )
        prev = last or GENESIS
        count = 0
        for e in db.scalars(
            select(AuditEntry).where(AuditEntry.hash.is_(None)).order_by(AuditEntry.id)
        ):
            e.prev_hash = prev
            e.hash = prev = entry_hash(prev, e)
            count += 1
        if count:
            db.commit()
        return count


def verify(db: Session) -> dict[str, Any]:
    """Prüft die ganze Kette. Gibt den ersten kaputten Eintrag zurück."""
    prev = GENESIS
    checked = 0
    for e in db.scalars(
        select(AuditEntry).where(AuditEntry.hash.is_not(None)).order_by(AuditEntry.id)
    ):
        if e.prev_hash != prev or e.hash != entry_hash(prev, e):
            return {"ok": False, "checked": checked, "broken_id": e.id, "last_hash": prev}
        prev = e.hash
        checked += 1
    return {"ok": True, "checked": checked, "broken_id": None, "last_hash": prev}
