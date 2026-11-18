"""Phase 6: Ablauf-Erinnerungen.

Einmal pro Stunde wird geprüft, was bald abläuft. Jede Erinnerung wird als Audit-Eintrag
festgehalten (daraus werden Benachrichtigungen) – je Gegenstand und Schwelle nur einmal.
"""

import asyncio
import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract import audit
from tesseract.db.models import Authority, CustomCert, Device, Node, Setting, utcnow

log = logging.getLogger("tesseract.reminders")

# Schwellen in Tagen
DEVICE_DAYS = (30, 7)
CA_DAYS = (90, 30, 7)
NODE_DAYS = (30, 7)
CUSTOM_DAYS = (21, 7)


def _sent(db: Session) -> dict[str, Any]:
    row = db.get(Setting, "reminders")
    return dict(row.value) if row else {}


def _save(db: Session, sent: dict[str, Any]) -> None:
    row = db.get(Setting, "reminders")
    if row is None:
        db.add(Setting(key="reminders", value=sent))
    else:
        row.value = sent


def _threshold(days_left: float, steps: tuple[int, ...]) -> int | None:
    hit = [s for s in steps if days_left <= s]
    return min(hit) if hit else None


def check(db: Session) -> list[str]:
    """Erzeugt fällige Erinnerungen (Commit macht der Aufrufer). Gibt deren Schlüssel zurück."""
    now = utcnow()
    sent = _sent(db)
    created: list[str] = []

    def remind(key: str, action: str, target: str, days: float, details: dict) -> None:
        if key in sent:
            return
        sent[key] = now.isoformat(timespec="seconds")
        audit.record(
            db,
            actor="system",
            action=action,
            target=target,
            details={"days": max(0, int(days)), **details},
        )
        created.append(key)

    for d in db.scalars(select(Device).where(Device.revoked_at.is_(None), Device.not_after > now)):
        left = (d.not_after - now).total_seconds() / 86400
        t = _threshold(left, DEVICE_DAYS)
        if t is not None:
            remind(
                f"device:{d.id}:{d.serial}:{t}",
                "device_expiring",
                f"{d.person.name} · {d.name}",
                left,
                {"not_after": d.not_after.isoformat(), "unlimited": d.unlimited},
            )

    for a in db.scalars(
        select(Authority).where(Authority.kind == "intermediate", Authority.active)
    ):
        left = (a.not_after - now).total_seconds() / 86400
        t = _threshold(left, CA_DAYS)
        if t is not None:
            remind(
                f"ca:{a.fingerprint[:16]}:{t}",
                "ca_expiring",
                "Geräte-Zwischenzertifikat",
                left,
                {"not_after": a.not_after.isoformat()},
            )

    for n in db.scalars(select(Node).where(Node.cert_not_after.is_not(None))):
        left = (n.cert_not_after - now).total_seconds() / 86400
        t = _threshold(left, NODE_DAYS)
        if t is not None:
            remind(
                f"node:{n.id}:{n.cert_fingerprint}:{t}",
                "node_cert_expiring",
                n.name,
                left,
                {"not_after": n.cert_not_after.isoformat()},
            )

    for c in db.scalars(select(CustomCert)):
        left = (c.not_after - now).total_seconds() / 86400
        t = _threshold(left, CUSTOM_DAYS)
        if t is not None:
            remind(
                f"custom:{c.id}:{c.fingerprint[:16]}:{t}",
                "custom_cert_expiring",
                c.name,
                left,
                {"not_after": c.not_after.isoformat()},
            )

    # Alte Einträge (über ein Jahr) vergessen
    cutoff = (now - timedelta(days=400)).isoformat()
    sent = {k: v for k, v in sent.items() if v >= cutoff}
    _save(db, sent)
    return created


async def watch(database, interval: float = 3600.0) -> None:
    while True:
        try:
            with database.sessionmaker() as db:
                if check(db):
                    db.commit()
                else:
                    db.rollback()
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover
            log.exception("Ablauf-Erinnerungen: Fehler")
        await asyncio.sleep(interval)
