"""Eigene Zertifikate hochladen (z. B. von einer Firmen-CA)."""

import hashlib
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from tesseract import audit, pki
from tesseract.certs import parse
from tesseract.db.models import CustomCert, Host
from tesseract.deps import DB, AppSettings, Box, CurrentActor
from tesseract.services import CUSTOM_KEY_CONTEXT, apply_all

router = APIRouter(prefix="/custom-certs", tags=["certificates"])

MAX_PEM = 64 * 1024


class CustomCertIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    certificate: str = Field(max_length=MAX_PEM)
    key: str = Field(max_length=MAX_PEM)


class CustomCertOut(BaseModel):
    id: int
    name: str
    names: list[str]
    issuer: str
    fingerprint: str
    not_before: datetime
    not_after: datetime
    used_by: list[str]
    created_at: datetime


def _validate(body: CustomCertIn) -> tuple[list[x509.Certificate], str]:
    """Kette prüfen, Schlüssel muss zum ersten Zertifikat passen."""
    try:
        chain = x509.load_pem_x509_certificates(body.certificate.encode())
    except ValueError as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Kein gültiges PEM-Zertifikat"
        ) from e
    try:
        key = serialization.load_pem_private_key(body.key.encode(), password=None)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Kein gültiger, unverschlüsselter PEM-Schlüssel",
        ) from e
    leaf = chain[0]
    pub = lambda k: k.public_bytes(  # noqa: E731
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    if pub(leaf.public_key()) != pub(key.public_key()):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Schlüssel passt nicht zum Zertifikat"
        )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return chain, key_pem


def _out(db, c: CustomCert) -> CustomCertOut:
    used = list(
        db.scalars(select(Host.domain).where(Host.custom_cert_id == c.id).order_by(Host.domain))
    )
    return CustomCertOut(
        id=c.id,
        name=c.name,
        names=c.names,
        issuer=c.issuer,
        fingerprint=pki.format_fingerprint(c.fingerprint),
        not_before=c.not_before,
        not_after=c.not_after,
        used_by=used,
        created_at=c.created_at,
    )


@router.get("")
def list_certs(db: DB, _: CurrentActor) -> list[CustomCertOut]:
    return [_out(db, c) for c in db.scalars(select(CustomCert).order_by(CustomCert.name))]


def _store(c: CustomCert, chain: list[x509.Certificate], key_pem: str, box) -> None:
    leaf = chain[0]
    info = parse(leaf.public_bytes(serialization.Encoding.DER))
    c.cert_pem = "".join(x.public_bytes(serialization.Encoding.PEM).decode() for x in chain)
    c.key_enc = box.encrypt(key_pem.encode(), CUSTOM_KEY_CONTEXT)
    c.names = info.names
    # „Firma GmbH · Firma Root CA“ – ohne doppelte Angaben, wenn es keinen CN gibt
    has_cn = not info.issuer.startswith(("O=", "CN=", "C="))
    c.issuer = " · ".join(x for x in (info.issuer_org, info.issuer if has_cn else "") if x)
    c.fingerprint = hashlib.sha256(leaf.public_bytes(serialization.Encoding.DER)).hexdigest()
    c.not_before, c.not_after = info.not_before, info.not_after


@router.post("", status_code=status.HTTP_201_CREATED)
def upload(body: CustomCertIn, db: DB, box: Box, actor: CurrentActor) -> CustomCertOut:
    chain, key_pem = _validate(body)
    c = CustomCert(name=body.name.strip())
    _store(c, chain, key_pem, box)
    db.add(c)
    audit.record(
        db,
        actor=actor.name,
        action="custom_cert_uploaded",
        target=c.name,
        details={"names": c.names, "not_after": c.not_after.isoformat()},
        ip=actor.ip,
    )
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ein Zertifikat mit diesem Namen gibt es schon"
        ) from e
    return _out(db, c)


@router.put("/{cert_id}")
def replace(
    cert_id: int,
    body: CustomCertIn,
    request: Request,
    db: DB,
    box: Box,
    actor: CurrentActor,
    settings: AppSettings,
) -> CustomCertOut:
    """Erneuertes Zertifikat einspielen – alle Hosts damit bekommen es sofort."""
    c = db.get(CustomCert, cert_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zertifikat nicht gefunden")
    chain, key_pem = _validate(body)
    c.name = body.name.strip()
    _store(c, chain, key_pem, box)
    audit.record(
        db,
        actor=actor.name,
        action="custom_cert_replaced",
        target=c.name,
        details={"not_after": c.not_after.isoformat()},
        ip=actor.ip,
    )
    db.commit()
    apply_all(db, settings, request.app.state.caddy_transport)
    db.commit()
    return _out(db, c)


@router.delete("/{cert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(cert_id: int, db: DB, actor: CurrentActor) -> None:
    c = db.get(CustomCert, cert_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zertifikat nicht gefunden")
    used = _out(db, c).used_by
    if used:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Wird noch genutzt von: {', '.join(used)}")
    audit.record(db, actor=actor.name, action="custom_cert_deleted", target=c.name, ip=actor.ip)
    db.delete(c)
    db.commit()
