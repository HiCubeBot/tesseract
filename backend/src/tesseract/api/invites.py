"""Einladungen – Admin-Seite (angemeldet) und Gast-Seite (öffentlich, nur mit Token)."""

import base64
import io
import secrets
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

import segno
from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract import audit
from tesseract.api.renew import renew_url
from tesseract.config import Settings
from tesseract.db.models import Enrollment, Host, Invite, Person, utcnow
from tesseract.deps import DB, AppSettings, Box, CurrentActor, client_ip
from tesseract.identity import CAError, active_device_count, ca_configured, issue_device
from tesseract.invites import (
    DEFAULT_DAYS,
    MAX_FAILED_CODES,
    check_code,
    create_invite,
    find_enrollment,
    find_invite,
    format_code,
    invite_code,
    invite_state,
    invite_token,
    open_requests,
    sha256,
)
from tesseract.secretbox import SecretBox
from tesseract.services import apply_all, granted_persons

admin = APIRouter(tags=["invites"])
public = APIRouter(prefix="/enroll", tags=["enroll"])


# ---------- Schemas ----------


class InviteIn(BaseModel):
    days: int = Field(DEFAULT_DAYS, ge=1, le=30)


class EnrollmentOut(BaseModel):
    id: int
    device_name: str
    platform: str
    user_agent: str
    ip: str | None
    status: Literal["pending", "approved", "rejected", "delivered"]
    created_at: datetime
    decided_at: datetime | None
    decided_by: str | None
    delivered_at: datetime | None


class InviteOut(BaseModel):
    id: int
    person_id: int
    person_name: str
    url: str
    code: str
    state: Literal["open", "expired", "revoked"]
    created_by: str
    created_at: datetime
    expires_at: datetime
    slots_left: int
    enrollments: list[EnrollmentOut]


class PublicInvite(BaseModel):
    person_name: str
    slots_left: int
    max_devices: int
    expires_at: datetime
    services: list[str]


class RegisterIn(BaseModel):
    device_name: str = Field(min_length=1, max_length=64)
    platform: str = Field("", max_length=32)
    code: str = Field(max_length=16)

    @field_validator("device_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Bitte einen Gerätenamen angeben")
        return v


class RegisterOut(BaseModel):
    enrollment_id: int
    secret: str


class EnrollStatus(BaseModel):
    status: str
    device_name: str


class Certificate(BaseModel):
    filename: str
    password: str
    p12_base64: str
    not_after: datetime
    services: list[str]
    slots_left: int
    # Link zum späteren Selbst-Verlängern (None = ausgeschaltet)
    renew_url: str | None = None


# ---------- Hilfen ----------


def public_base(request: Request, settings: Settings) -> str:
    """Adresse, unter der Gäste den Controller erreichen."""
    if settings.controller_domain:
        return f"https://{settings.controller_domain}"
    for header in ("origin", "referer"):
        value = request.headers.get(header)
        if value:
            parts = urlsplit(value)
            if parts.scheme in ("http", "https") and parts.netloc:
                return f"{parts.scheme}://{parts.netloc}"
    return str(request.base_url).rstrip("/")


def slots_left(db: Session, person: Person, invite: Invite | None = None) -> int:
    used = active_device_count(db, person.id)
    pending = open_requests(invite) if invite else 0
    return max(0, person.max_devices - used - pending)


def services_for(db: Session, person: Person) -> list[str]:
    """Hosts, die die Person (direkt oder per Gruppe) mit Zertifikat erreicht."""
    out = []
    for host in db.scalars(select(Host).where(Host.enabled, Host.draft.is_(False))):
        if (host.access == "mtls" or host.paths) and any(
            p.id == person.id for p in granted_persons(db, host)
        ):
            out.append(host.domain)
    return sorted(out)


def invite_out(db: Session, box: SecretBox, invite: Invite, base: str) -> InviteOut:
    return InviteOut(
        id=invite.id,
        person_id=invite.person_id,
        person_name=invite.person.name,
        url=f"{base}/e/{invite_token(box, invite)}",
        code=format_code(invite_code(box, invite)),
        state=invite_state(invite),  # type: ignore[arg-type]
        created_by=invite.created_by,
        created_at=invite.created_at,
        expires_at=invite.expires_at,
        slots_left=slots_left(db, invite.person, invite),
        enrollments=[
            EnrollmentOut.model_validate(e, from_attributes=True) for e in invite.enrollments
        ],
    )


def _get_invite(db: Session, invite_id: int) -> Invite:
    invite = db.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Einladung nicht gefunden")
    return invite


# ---------- Admin ----------


@admin.post("/persons/{person_id}/invites", status_code=status.HTTP_201_CREATED)
def create(
    person_id: int,
    body: InviteIn,
    request: Request,
    db: DB,
    box: Box,
    actor: CurrentActor,
    settings: AppSettings,
) -> InviteOut:
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person nicht gefunden")
    if person.disabled:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{person.name} ist gesperrt")
    if not ca_configured(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "Erst die Zertifizierungsstelle einrichten")
    invite, _, _ = create_invite(db, box, person, actor=actor.name, days=body.days)
    db.flush()
    audit.record(
        db,
        actor=actor.name,
        action="invite_created",
        target=person.name,
        details={"invite": invite.id, "expires_at": invite.expires_at.isoformat()},
        ip=actor.ip,
    )
    db.commit()
    return invite_out(db, box, invite, public_base(request, settings))


@admin.get("/invites")
def list_invites(
    request: Request, db: DB, box: Box, _: CurrentActor, settings: AppSettings, all: bool = False
) -> list[InviteOut]:
    base = public_base(request, settings)
    invites = db.scalars(select(Invite).order_by(Invite.id.desc())).all()
    out = [invite_out(db, box, i, base) for i in invites]
    return out if all else [i for i in out if i.state == "open"]


@admin.get("/invites/{invite_id}")
def get_invite(
    invite_id: int, request: Request, db: DB, box: Box, _: CurrentActor, settings: AppSettings
) -> InviteOut:
    return invite_out(db, box, _get_invite(db, invite_id), public_base(request, settings))


@admin.get("/invites/{invite_id}/qr.svg")
def invite_qr(
    invite_id: int, request: Request, db: DB, box: Box, _: CurrentActor, settings: AppSettings
) -> Response:
    invite = _get_invite(db, invite_id)
    url = f"{public_base(request, settings)}/e/{invite_token(box, invite)}"
    buf = io.BytesIO()
    segno.make(url, error="m").save(
        buf, kind="svg", scale=6, border=2, dark="#0e1014", light="#ffffff"
    )
    return Response(
        buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"}
    )


@admin.post("/invites/{invite_id}/revoke")
def revoke_invite(
    invite_id: int, request: Request, db: DB, box: Box, actor: CurrentActor, settings: AppSettings
) -> InviteOut:
    invite = _get_invite(db, invite_id)
    if invite.revoked_at is None:
        invite.revoked_at = utcnow()
        for e in invite.enrollments:
            if e.status == "pending":
                e.status, e.decided_at, e.decided_by = "rejected", utcnow(), actor.name
        audit.record(
            db, actor=actor.name, action="invite_revoked", target=invite.person.name, ip=actor.ip
        )
        db.commit()
    return invite_out(db, box, invite, public_base(request, settings))


def _decide(db: Session, enrollment_id: int, approve: bool, actor) -> Enrollment:
    e = db.get(Enrollment, enrollment_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anfrage nicht gefunden")
    if e.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Über diese Anfrage wurde schon entschieden")
    if approve and invite_state(e.invite) != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "Die Einladung ist nicht mehr gültig")
    e.status = "approved" if approve else "rejected"
    e.decided_at, e.decided_by = utcnow(), actor.name
    audit.record(
        db,
        actor=actor.name,
        action="enrollment_approved" if approve else "enrollment_rejected",
        target=f"{e.invite.person.name} · {e.device_name}",
        details={"platform": e.platform, "ip": e.ip},
        ip=actor.ip,
    )
    db.commit()
    return e


@admin.post("/enrollments/{enrollment_id}/approve")
def approve(enrollment_id: int, db: DB, actor: CurrentActor) -> EnrollmentOut:
    return EnrollmentOut.model_validate(
        _decide(db, enrollment_id, True, actor), from_attributes=True
    )


@admin.post("/enrollments/{enrollment_id}/reject")
def reject(enrollment_id: int, db: DB, actor: CurrentActor) -> EnrollmentOut:
    return EnrollmentOut.model_validate(
        _decide(db, enrollment_id, False, actor), from_attributes=True
    )


# ---------- Gast (öffentlich) ----------


def _open_invite(db: Session, token: str) -> Invite:
    invite = find_invite(db, token)
    # Gleiche Antwort für unbekannt, abgelaufen und widerrufen – verrät nichts
    if invite is None or invite_state(invite) != "open" or invite.person.disabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diese Einladung ist nicht (mehr) gültig")
    return invite


def _throttle(request: Request) -> str:
    ip = client_ip(request) or "?"
    if request.app.state.enroll_throttle.blocked(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Zu viele Versuche – bitte warten")
    return ip


@public.get("/{token}")
def public_invite(token: str, request: Request, db: DB) -> PublicInvite:
    _throttle(request)
    invite = _open_invite(db, token)
    person = invite.person
    return PublicInvite(
        person_name=person.name,
        slots_left=slots_left(db, person, invite),
        max_devices=person.max_devices,
        expires_at=invite.expires_at,
        services=services_for(db, person),
    )


@public.post("/{token}/register", status_code=status.HTTP_201_CREATED)
def register(token: str, body: RegisterIn, request: Request, db: DB, box: Box) -> RegisterOut:
    ip = _throttle(request)
    invite = _open_invite(db, token)
    if not check_code(box, invite, body.code):
        request.app.state.enroll_throttle.fail(ip)
        invite.failed_attempts += 1
        locked = invite.failed_attempts >= MAX_FAILED_CODES
        if locked:
            invite.revoked_at = utcnow()
        audit.record(
            db,
            actor="Gast",
            action="enrollment_code_wrong",
            target=invite.person.name,
            details={"attempt": invite.failed_attempts, "locked": locked},
            ip=ip,
        )
        db.commit()
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Zu viele falsche Codes – die Einladung ist gesperrt"
            if locked
            else "Der Bestätigungscode stimmt nicht",
        )
    if slots_left(db, invite.person, invite) <= 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Es ist kein Platz für ein weiteres Gerät frei"
        )
    secret = secrets.token_urlsafe(24)
    e = Enrollment(
        invite_id=invite.id,
        device_name=body.device_name,
        platform=body.platform,
        user_agent=(request.headers.get("user-agent") or "")[:255],
        ip=ip,
        secret_hash=sha256(secret),
    )
    db.add(e)
    db.flush()
    audit.record(
        db,
        actor=invite.person.name,
        action="enrollment_requested",
        target=f"{invite.person.name} · {body.device_name}",
        details={"platform": body.platform},
        ip=ip,
    )
    db.commit()
    return RegisterOut(enrollment_id=e.id, secret=secret)


def _guest_enrollment(db: Session, token: str, enrollment_id: int, secret: str) -> Enrollment:
    invite = find_invite(db, token)
    e = find_enrollment(invite, enrollment_id, secret) if invite else None
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anfrage nicht gefunden")
    return e


Secret = Annotated[str, Header(alias="X-Enroll-Secret", max_length=64)]


@public.get("/{token}/requests/{enrollment_id}")
def request_status(
    token: str, enrollment_id: int, secret: Secret, request: Request, db: DB
) -> EnrollStatus:
    _throttle(request)
    e = _guest_enrollment(db, token, enrollment_id, secret)
    return EnrollStatus(status=e.status, device_name=e.device_name)


@public.post("/{token}/requests/{enrollment_id}/certificate")
def certificate(
    token: str,
    enrollment_id: int,
    secret: Secret,
    request: Request,
    db: DB,
    box: Box,
    settings: AppSettings,
) -> Certificate:
    """Stellt das Zertifikat genau einmal aus – der Schlüssel wird nicht gespeichert."""
    ip = _throttle(request)
    e = _guest_enrollment(db, token, enrollment_id, secret)
    if e.status == "delivered":
        raise HTTPException(
            status.HTTP_410_GONE,
            "Das Zertifikat wurde bereits abgeholt. Für ein neues bitte erneut registrieren.",
        )
    if e.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Die Anfrage ist noch nicht freigegeben")
    person = e.invite.person
    try:
        issued = issue_device(db, box, person, name=e.device_name, platform=e.platform)
    except CAError as err:
        raise HTTPException(status.HTTP_409_CONFLICT, str(err)) from err
    db.flush()
    e.status, e.delivered_at, e.device_id = "delivered", utcnow(), issued.device.id
    audit.record(
        db,
        actor=person.name,
        action="device_issued",
        target=f"{person.name} · {e.device_name}",
        details={"serial": issued.device.serial, "via": "Einladung"},
        ip=ip,
    )
    db.commit()
    apply_all(db, settings, request.app.state.caddy_transport)
    db.commit()
    return Certificate(
        filename=issued.filename,
        password=issued.password,
        p12_base64=base64.b64encode(issued.p12).decode(),
        not_after=issued.device.not_after,
        services=services_for(db, person),
        slots_left=slots_left(db, person, e.invite),
        renew_url=renew_url(public_base(request, settings), db),
    )
