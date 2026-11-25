"""FastAPI-Abhängigkeiten: DB-Session, angemeldeter Admin."""

import hashlib
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from tesseract.auth import SESSION_COOKIE, session_for_token
from tesseract.caddy.config import FINGERPRINT_HEADER
from tesseract.config import Settings
from tesseract.db import Database
from tesseract.db.models import Admin, Device
from tesseract.secretbox import SecretBox
from tesseract.services import admin_devices, get_general


def get_db(request: Request) -> Iterator[Session]:
    database: Database = request.app.state.db
    yield from database.session()


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_secretbox(request: Request) -> SecretBox:
    return request.app.state.secretbox


DB = Annotated[Session, Depends(get_db)]
Box = Annotated[SecretBox, Depends(get_secretbox)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]


@dataclass
class Actor:
    """Wer eine Anfrage stellt: ein Admin-Konto (Sitzung) oder eine Person per Zertifikat."""

    admin: Admin | None
    ip: str | None
    # "admin" für Konten; bei Personen ihre Rolle (siehe uiaccess.py)
    role: str = "admin"
    person_id: int | None = None
    person_name: str = ""
    device_name: str = ""

    @property
    def name(self) -> str:
        if self.admin is not None:
            return self.admin.username
        # im Audit-Log: Person und Gerät statt „admin“
        return f"{self.person_name} ({self.device_name})"

    @property
    def account(self) -> Admin:
        """Das Admin-Konto – Passwort, Passkeys & Co. gibt es nur dort."""
        if self.admin is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Nur für Admin-Konten – du bist per Gerätezertifikat angemeldet",
            )
        return self.admin


_FP_RE = re.compile(r"[0-9a-f]{64}")
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def client_fingerprint(request: Request) -> str:
    """Fingerabdruck des Client-Zertifikats – setzt Caddy (überschreibt Client-Header)."""
    value = request.headers.get(FINGERPRINT_HEADER, "").strip().lower()
    # Ohne Zertifikat liefert Caddy den SHA-256 eines leeren Inhalts – das zählt nicht
    if value == _EMPTY_SHA256 or not _FP_RE.fullmatch(value):
        return ""
    return value


def admin_device_for(request: Request, db: Session) -> Device | None:
    fp = client_fingerprint(request)
    if not fp:
        return None
    return next((d for d in admin_devices(db) if d.fingerprint == fp), None)


def require_admin_device(request: Request, db: Session) -> None:
    """Ist „Oberfläche nur mit Admin-Zertifikat“ an, muss die Anfrage eines mitbringen.
    Caddy prüft das schon; das hier ist die zweite Linie."""
    if get_general(db)["admin_mtls"] and admin_device_for(request, db) is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Die Oberfläche ist nur mit einem Admin-Zertifikat erreichbar",
        )


def cert_actor(request: Request, db: Session) -> Actor | None:
    """Person mit Zugriff auf Tesseract, erkannt am Gerätezertifikat (ohne Sitzung)."""
    from tesseract import uiaccess

    device = uiaccess.device_for(db, client_fingerprint(request))
    if device is None:
        return None
    return Actor(
        admin=None,
        ip=client_ip(request),
        role=device.person.ui_role,
        person_id=device.person_id,
        person_name=device.person.name,
        device_name=device.name,
    )


def current_actor(request: Request, db: DB) -> Actor:
    token = request.cookies.get(SESSION_COOKIE)
    session = session_for_token(db, token) if token else None
    if session is not None:
        require_admin_device(request, db)
        return Actor(admin=session.admin, ip=client_ip(request))
    actor = cert_actor(request, db)
    if actor is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nicht angemeldet")
    from tesseract import uiaccess

    if not uiaccess.allowed(actor.role, request.method, request.url.path):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Deine Rolle „{uiaccess.ROLE_LABELS.get(actor.role, actor.role)}“ darf das nicht",
        )
    return actor


CurrentActor = Annotated[Actor, Depends(current_actor)]
