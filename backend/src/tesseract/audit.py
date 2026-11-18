"""Audit-Log (Basis). Phase 5 ergänzt verkettete Prüfsummen."""

from typing import Any

from sqlalchemy.orm import Session

from tesseract.db.models import AuditEntry


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
