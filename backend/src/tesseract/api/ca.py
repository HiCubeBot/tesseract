from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from tesseract import audit, pki
from tesseract.db.models import Authority, Device
from tesseract.deps import DB, Box, CurrentActor
from tesseract.identity import MIN_ROOT_PASSPHRASE, CAError, active_authority, setup_ca

router = APIRouter(prefix="/ca", tags=["ca"])


class AuthorityOut(BaseModel):
    kind: str
    subject: str
    fingerprint: str
    not_before: datetime
    not_after: datetime
    key_on_controller: bool


class CAStatus(BaseModel):
    configured: bool
    root: AuthorityOut | None
    intermediate: AuthorityOut | None
    devices_total: int
    devices_active: int
    devices_revoked: int
    # Geräte, die länger gültig wären als das Zwischenzertifikat (wirken nur bis dahin)
    devices_beyond_intermediate: int


class SetupIn(BaseModel):
    passphrase: str = Field(min_length=MIN_ROOT_PASSPHRASE, max_length=256)


class SetupOut(BaseModel):
    root_cert_pem: str
    root_key_pem: str


def _cn(cert) -> str:
    from cryptography.x509.oid import NameOID

    attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    return str(attrs[0].value) if attrs else cert.subject.rfc4514_string()


def _out(a: Authority | None) -> AuthorityOut | None:
    if a is None:
        return None
    cert = pki.load_cert(a.cert_pem)
    return AuthorityOut(
        kind=a.kind,
        subject=_cn(cert),
        fingerprint=pki.format_fingerprint(a.fingerprint),
        not_before=a.not_before,
        not_after=a.not_after,
        key_on_controller=a.key_enc is not None,
    )


@router.get("")
def ca_status(db: DB, _: CurrentActor) -> CAStatus:
    root = active_authority(db, "root")
    inter = active_authority(db, "intermediate")
    total = db.scalar(select(func.count()).select_from(Device)) or 0
    revoked = (
        db.scalar(select(func.count()).select_from(Device).where(Device.revoked_at.is_not(None)))
        or 0
    )
    active = sum(1 for d in db.scalars(select(Device)) if d.status == "active")
    beyond = 0
    if inter is not None:
        beyond = (
            db.scalar(
                select(func.count())
                .select_from(Device)
                .where(Device.unlimited, Device.revoked_at.is_(None))
            )
            or 0
        )
    return CAStatus(
        configured=inter is not None,
        root=_out(root),
        intermediate=_out(inter),
        devices_total=total,
        devices_active=active,
        devices_revoked=revoked,
        devices_beyond_intermediate=beyond,
    )


@router.post("/setup")
def setup(body: SetupIn, db: DB, box: Box, actor: CurrentActor) -> SetupOut:
    try:
        result = setup_ca(db, box, body.passphrase)
    except CAError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    audit.record(db, actor=actor.name, action="ca_created", target="Tesseract Root CA", ip=actor.ip)
    db.commit()
    return SetupOut(root_cert_pem=result.root_cert_pem, root_key_pem=result.root_key_pem)


@router.get("/root.pem", response_class=PlainTextResponse)
def root_pem(db: DB, _: CurrentActor) -> PlainTextResponse:
    root = active_authority(db, "root")
    if root is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Noch keine CA eingerichtet")
    return PlainTextResponse(
        root.cert_pem,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": 'attachment; filename="tesseract-root-ca.pem"'},
    )
