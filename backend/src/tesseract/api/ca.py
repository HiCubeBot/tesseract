from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from tesseract import audit, pki
from tesseract.db.models import Authority, Device
from tesseract.deps import DB, AppSettings, Box, CurrentActor
from tesseract.identity import (
    MIN_ROOT_PASSPHRASE,
    CAError,
    active_authority,
    devices_of,
    install_ca,
    nodes_of,
    rotate_intermediate,
    rotate_root,
    setup_ca,
    trusted_intermediates,
)
from tesseract.services import apply_all

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
    # Ältere Zwischenzertifikate, denen nach einem Wechsel noch vertraut wird
    previous: list["PreviousOut"] = []


class PreviousOut(BaseModel):
    authority: AuthorityOut
    # aktive Geräte, die noch daran hängen – nach dem Verlängern fällt es weg
    devices: list[dict]
    # Nodes mit Zertifikat davon – die Agents erneuern es nach einem Wechsel von selbst
    nodes: list[dict] = []


class RotateIn(BaseModel):
    root_key_pem: str = Field(min_length=50, max_length=10_000)
    # leer bei einem unverschlüsselten (importierten) Root-Schlüssel
    passphrase: str = Field("", max_length=256)


class ImportIn(BaseModel):
    """Bestehende CA: Root-Zertifikat plus Root-Schlüssel – oder plus fertigem
    Zwischenzertifikat mit Schlüssel (der Root-Schlüssel bleibt dann außerhalb)."""

    root_cert_pem: str = Field(min_length=50, max_length=20_000)
    root_key_pem: str = Field("", max_length=20_000)
    passphrase: str = Field("", max_length=256)
    intermediate_cert_pem: str = Field("", max_length=20_000)
    intermediate_key_pem: str = Field("", max_length=20_000)
    intermediate_passphrase: str = Field("", max_length=256)


class RotateRootIn(ImportIn):
    # "generate": neue Root erzeugen (Passphrase für den neuen Root-Schlüssel), "import":
    # vorhandene Root übernehmen (Felder wie beim Import)
    mode: Literal["generate", "import"]
    root_cert_pem: str = Field("", max_length=20_000)


class RotateRootOut(BaseModel):
    status: "CAStatus"
    # nur bei mode=generate: neuer Root, Schlüssel mit der Passphrase verschlüsselt
    root_cert_pem: str | None = None
    root_key_pem: str | None = None


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
        # unbegrenzte Geräte und alle, die das Zwischenzertifikat überdauern würden
        beyond = (
            db.scalar(
                select(func.count())
                .select_from(Device)
                .where(
                    Device.revoked_at.is_(None),
                    (Device.unlimited) | (Device.not_after >= inter.not_after),
                )
            )
            or 0
        )
    previous = [
        PreviousOut(
            authority=_out(a),
            devices=[
                {"id": d.id, "name": d.name, "person": d.person.name}
                for d in devices_of(db, a, active_only=True)
            ],
            nodes=[{"id": n.id, "name": n.name} for n in nodes_of(db, a)],
        )
        for a in trusted_intermediates(db)
        if not a.active
    ]
    return CAStatus(
        configured=inter is not None,
        root=_out(root),
        intermediate=_out(inter),
        devices_total=total,
        devices_active=active,
        devices_revoked=revoked,
        devices_beyond_intermediate=beyond,
        previous=previous,
    )


@router.post("/setup")
def setup(
    body: SetupIn,
    request: Request,
    db: DB,
    box: Box,
    actor: CurrentActor,
    settings: AppSettings,
) -> SetupOut:
    try:
        result = setup_ca(db, box, body.passphrase)
    except CAError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    audit.record(db, actor=actor.name, action="ca_created", target="Tesseract Root CA", ip=actor.ip)
    db.commit()
    # Caddy muss ab jetzt nach Client-Zertifikaten fragen (Admin-Geräte, Agents) – sonst erst
    # nach der nächsten Änderung
    apply_all(db, settings, request.app.state.caddy_transport)
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


@router.post("/rotate")
def rotate(
    body: RotateIn, request: Request, db: DB, box: Box, actor: CurrentActor, settings: AppSettings
) -> CAStatus:
    """Wechsel auf ein neues Zwischenzertifikat. Der Root-Schlüssel (aus der Einrichtung, mit
    Passphrase verschlüsselt) wird nur dafür benutzt und nicht gespeichert."""
    try:
        new = rotate_intermediate(db, box, body.root_key_pem, body.passphrase)
    except CAError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    audit.record(
        db,
        actor=actor.name,
        action="ca_rotated",
        target="Geräte-Zwischenzertifikat",
        details={"fingerprint": new.fingerprint[:16], "not_after": new.not_after.isoformat()},
        ip=actor.ip,
    )
    db.commit()
    # Caddy vertraut ab jetzt neuem und altem Zwischenzertifikat
    apply_all(db, settings, request.app.state.caddy_transport)
    db.commit()
    return ca_status(db, actor)


def _import_args(body: ImportIn) -> dict:
    return body.model_dump(
        include={
            "root_cert_pem",
            "root_key_pem",
            "passphrase",
            "intermediate_cert_pem",
            "intermediate_key_pem",
            "intermediate_passphrase",
        }
    )


def _details(new: Authority, how: str) -> dict:
    return {
        "how": how,
        "fingerprint": new.fingerprint[:16],
        "not_after": new.not_after.isoformat(),
    }


@router.post("/import")
def import_ca(
    body: ImportIn, request: Request, db: DB, box: Box, actor: CurrentActor, settings: AppSettings
) -> CAStatus:
    """Bestehende CA übernehmen statt eine neue zu erzeugen (nur vor der Einrichtung)."""
    try:
        new = install_ca(db, box, **_import_args(body))
    except CAError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    how = "intermediate" if body.intermediate_cert_pem.strip() else "root_key"
    root = active_authority(db, "root")
    audit.record(
        db,
        actor=actor.name,
        action="ca_imported",
        target=_out(root).subject if root else "Root-CA",
        details=_details(new, how),
        ip=actor.ip,
    )
    db.commit()
    apply_all(db, settings, request.app.state.caddy_transport)
    db.commit()
    return ca_status(db, actor)


@router.post("/rotate-root")
def rotate_root_ca(
    body: RotateRootIn,
    request: Request,
    db: DB,
    box: Box,
    actor: CurrentActor,
    settings: AppSettings,
) -> RotateRootOut:
    """Wechsel der Root-CA – neu erzeugt oder importiert. Das alte Zwischenzertifikat bleibt
    vertraut, bis Geräte verlängert und die Nodes erneuert sind."""
    result = None
    try:
        if body.mode == "generate":
            result = rotate_root(db, box, body.passphrase)
            new = active_authority(db, "intermediate")
        else:
            if not body.root_cert_pem.strip():
                raise CAError("Root-Zertifikat fehlt")
            new = install_ca(db, box, replace=True, **_import_args(body))
    except CAError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    root = active_authority(db, "root")
    audit.record(
        db,
        actor=actor.name,
        action="ca_root_rotated",
        target=_out(root).subject if root else "Root-CA",
        details=_details(new, body.mode),
        ip=actor.ip,
    )
    db.commit()
    # Caddy vertraut ab jetzt neuem und altem Zwischenzertifikat
    apply_all(db, settings, request.app.state.caddy_transport)
    db.commit()
    return RotateRootOut(
        status=ca_status(db, actor),
        root_cert_pem=result.root_cert_pem if result else None,
        root_key_pem=result.root_key_pem if result else None,
    )
