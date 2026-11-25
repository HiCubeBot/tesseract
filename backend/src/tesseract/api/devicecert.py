"""Zertifikate der Geräte später wieder abrufen: .p12 und Passwort, Download-Link fürs Handy.

Seit 1.22 legt Tesseract die .p12 und ihr Passwort verschlüsselt ab (abschaltbar unter
Einstellungen › Zertifizierungsstelle). Der Download-Link gilt 15 Minuten und höchstens drei
Abrufe – das Passwort steht nie im Link, es wird am Handy eingetippt.
"""

import base64
import io
import secrets
import time
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from tesseract import audit
from tesseract.api.invites import public_base, qr_svg
from tesseract.db.models import Device
from tesseract.deps import DB, AppSettings, Box, CurrentActor, client_ip
from tesseract.identity import P12_CONTEXT, p12_filename

router = APIRouter(tags=["devices"])
public = APIRouter(tags=["devices"])

LINK_SECONDS = 15 * 60
LINK_USES = 3


@dataclass
class Link:
    device_id: int
    expires: float
    uses: int = LINK_USES


class StoredCert(BaseModel):
    filename: str
    password: str
    p12_base64: str


class DownloadLink(BaseModel):
    url: str
    expires_at: float
    uses: int
    qr_svg: str


def _device(db, device_id: int) -> Device:
    d = db.get(Device, device_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gerät nicht gefunden")
    return d


def _stored(d: Device) -> None:
    if not d.p12_enc or not d.p12_password_enc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Für dieses Gerät ist kein Zertifikat hinterlegt – „Verlängern“ stellt ein neues aus",
        )
    if d.status == "revoked":
        raise HTTPException(status.HTTP_409_CONFLICT, "Das Gerät ist gesperrt")


def _links(request: Request) -> dict[str, Link]:
    if not hasattr(request.app.state, "p12_links"):
        request.app.state.p12_links = {}
    links: dict[str, Link] = request.app.state.p12_links
    now = time.time()
    for token in [t for t, link in links.items() if link.expires < now or link.uses <= 0]:
        del links[token]
    return links


@router.get("/devices/{device_id}/certificate")
def get_certificate(device_id: int, db: DB, box: Box, actor: CurrentActor) -> StoredCert:
    """Hinterlegte .p12 samt Passwort (wird im Audit-Log vermerkt)."""
    d = _device(db, device_id)
    _stored(d)
    audit.record(
        db,
        actor=actor.name,
        action="device_cert_viewed",
        target=f"{d.person.name} · {d.name}",
        ip=actor.ip,
    )
    db.commit()
    return StoredCert(
        filename=p12_filename(d),
        password=box.decrypt(d.p12_password_enc, P12_CONTEXT).decode(),
        p12_base64=base64.b64encode(box.decrypt(d.p12_enc, P12_CONTEXT)).decode(),
    )


@router.delete("/devices/{device_id}/certificate", status_code=status.HTTP_204_NO_CONTENT)
def forget_certificate(device_id: int, request: Request, db: DB, actor: CurrentActor) -> None:
    """Hinterlegte Kopie löschen – das Zertifikat selbst bleibt gültig."""
    d = _device(db, device_id)
    d.p12_enc = None
    d.p12_password_enc = None
    for token in [t for t, link in _links(request).items() if link.device_id == d.id]:
        del request.app.state.p12_links[token]
    audit.record(
        db,
        actor=actor.name,
        action="device_cert_forgotten",
        target=f"{d.person.name} · {d.name}",
        ip=actor.ip,
    )
    db.commit()


@router.post("/devices/{device_id}/download-link")
def download_link(
    device_id: int, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> DownloadLink:
    """Kurzlebiger Link (15 Min., 3 Abrufe) zum Herunterladen auf ein anderes Gerät, z. B. per
    QR-Code aufs Handy. Das Passwort steht nicht im Link."""
    d = _device(db, device_id)
    _stored(d)
    token = secrets.token_urlsafe(24)
    expires = time.time() + LINK_SECONDS
    _links(request)[token] = Link(d.id, expires)
    url = f"{public_base(request, settings)}/api/dl/{token}"
    buf = io.BytesIO()
    qr_svg(url, buf)
    audit.record(
        db,
        actor=actor.name,
        action="device_cert_link",
        target=f"{d.person.name} · {d.name}",
        ip=actor.ip,
    )
    db.commit()
    return DownloadLink(url=url, expires_at=expires, uses=LINK_USES, qr_svg=buf.getvalue().decode())


@public.get("/dl/{token}")
def download(token: str, request: Request, db: DB, box: Box) -> Response:
    """Öffentlicher Abruf über den Link – ohne Anmeldung, zeitlich und in der Anzahl begrenzt."""
    link = _links(request).get(token)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link abgelaufen oder ungültig")
    d = db.get(Device, link.device_id)
    if d is None or not d.p12_enc or d.status == "revoked":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link abgelaufen oder ungültig")
    link.uses -= 1
    audit.record(
        db,
        actor="Download-Link",
        action="device_cert_downloaded",
        target=f"{d.person.name} · {d.name}",
        ip=client_ip(request),
    )
    db.commit()
    return Response(
        box.decrypt(d.p12_enc, P12_CONTEXT),
        media_type="application/x-pkcs12",
        headers={
            "Content-Disposition": f'attachment; filename="{p12_filename(d)}"',
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
        },
    )
