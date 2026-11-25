"""Zugriff auf Tesseract für einzelne Personen – ausschließlich per Gerätezertifikat (mTLS).

Eine Person mit Rolle ≠ „none“ öffnet die Oberfläche von jedem ihrer aktiven Geräte aus, ohne
Passwort und ohne Login-Formular. Caddy reicht den Fingerabdruck des Client-Zertifikats durch
(`X-Tesseract-Client-Fingerprint`), der Controller ordnet ihn Gerät → Person → Rolle zu – bei
**jeder** Anfrage, es gibt keine Sitzung. Gesperrte oder abgelaufene Geräte und gesperrte
Personen verlieren den Zugriff damit sofort.

Rollen:
- `read`   Lesen: Übersicht, Hosts, Statistik, Logs, Uptime – keine Änderungen, keine Geheimnisse
- `own`    Eigene Dienste: nur die Hosts, für die die Person freigegeben ist (Details, Verlauf,
           Statistik), dazu die eigenen Geräte
- `admin`  wie ein Admin-Konto (nur Konto-Funktionen wie Passwort und Passkeys fehlen)

Die Rechte prüft `allowed()` zentral für jede API-Anfrage (Positivliste – alles andere ist für
`read`/`own` verboten). Welche Hosts bei `own` sichtbar sind, filtern die Endpunkte selbst
über `visible_host_ids()`.
"""

import re
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.db.models import Device, Host, Person

if TYPE_CHECKING:
    from tesseract.deps import Actor

ROLES = ("none", "read", "own", "admin")
ROLE_LABELS = {
    "none": "Kein Zugriff",
    "read": "Lesen",
    "own": "Eigene Dienste",
    "admin": "Admin",
}

_ALWAYS = [
    r"/api/auth/(me|device|methods)",
]
_READ_GET = [
    *_ALWAYS,
    r"/api/counts",
    r"/api/hosts",
    r"/api/hosts/\d+",
    r"/api/hosts/\d+/versions(/\d+)?",
    r"/api/nodes",
    r"/api/stats/[a-z-]+",
    r"/api/logs(/\d+)?",
    r"/api/monitor",
    r"/api/certificates",
    r"/api/me/devices",
]
_OWN_GET = [
    *_ALWAYS,
    r"/api/hosts",
    r"/api/hosts/\d+",
    r"/api/hosts/\d+/versions(/\d+)?",
    r"/api/stats/(host|activity)",
    r"/api/me/devices",
]
_ANY_METHOD = [r"/api/auth/logout"]


def _match(patterns: list[str], path: str) -> bool:
    return any(re.fullmatch(p, path) for p in patterns)


def allowed(role: str, method: str, path: str) -> bool:
    """Darf diese Rolle diese Anfrage stellen? (Pfad ohne Query-String)"""
    if role == "admin":
        return True
    if _match(_ANY_METHOD, path):
        return True
    if method not in ("GET", "HEAD"):
        return False
    if role == "read":
        return _match(_READ_GET, path)
    if role == "own":
        return _match(_OWN_GET, path)
    return False


def device_for(db: Session, fingerprint: str) -> Device | None:
    """Aktives Gerät einer nicht gesperrten Person mit Zugriff auf Tesseract."""
    if not fingerprint:
        return None
    d = db.scalar(select(Device).where(Device.fingerprint == fingerprint))
    if d is None or d.status != "active":
        return None
    p = d.person
    if p.disabled or (p.ui_role or "none") == "none":
        return None
    return d


def ui_devices(db: Session) -> list[Device]:
    """Alle Geräte, mit denen jemand die Oberfläche öffnen darf (für „nur mit Zertifikat“)."""
    persons = db.scalars(
        select(Person).where(Person.ui_role != "none", Person.disabled.is_(False))
    ).all()
    return [d for p in persons for d in p.devices if d.status == "active"]


def granted_host_ids(db: Session, person_id: int) -> set[int]:
    """Hosts, für die die Person freigegeben ist (direkt, über Gruppen oder einen Bereich)."""
    from tesseract.services import granted_persons

    out: set[int] = set()
    for h in db.scalars(select(Host)):
        if any(p.id == person_id for p in granted_persons(db, h)):
            out.add(h.id)
            continue
        for a in h.areas:
            if person_id in (a.grant_person_ids or []):
                out.add(h.id)
                break
            group_ids = set(a.grant_group_ids or [])
            if group_ids and db.scalar(
                select(Person.id)
                .where(Person.id == person_id)
                .where(Person.groups.any(_group_in(group_ids)))
            ):
                out.add(h.id)
                break
    return out


def _group_in(ids: set[int]):
    from tesseract.db.models import Group

    return Group.id.in_(ids)


def visible_host_ids(db: Session, actor: "Actor") -> set[int] | None:
    """None = alle Hosts; sonst nur diese (Rolle „Eigene Dienste“)."""
    if actor.role != "own" or actor.person_id is None:
        return None
    return granted_host_ids(db, actor.person_id)
