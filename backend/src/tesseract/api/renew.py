"""Gäste verlängern ihr Gerät selbst (öffentlich, ohne Anmeldung).

Der Link `https://<controller>/v` wird auf dem Gerät geöffnet, das verlängert werden soll.
Caddy fragt auf der Controller-Domain nach einem Client-Zertifikat und reicht dessen
Fingerabdruck weiter – das noch gültige Zertifikat ist der Ausweis. Ohne Zertifikat (anderes
Gerät, schon abgelaufen, gesperrt) gibt es nichts. Erlaubt ist das Verlängern erst kurz vor
Ablauf (`device_self_renew_days`), bei Geräten eines alten Zwischenzertifikats jederzeit.
Abschaltbar unter Einstellungen › Zertifizierungsstelle.
"""

import base64
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from tesseract import audit, pki
from tesseract.db.models import Device, utcnow
from tesseract.deps import DB, AppSettings, Box, client_fingerprint, client_ip
from tesseract.identity import DEFAULT_DEVICE_DAYS, CAError, active_authority, renew_device
from tesseract.services import apply_all, get_general

public = APIRouter(prefix="/renew", tags=["renew"])

PATH = "/v"


class RenewStatus(BaseModel):
    enabled: bool
    # Gerätezertifikat erkannt?
    recognized: bool
    device: str | None = None
    person: str | None = None
    not_after: datetime | None = None
    days_left: int | None = None
    can_renew: bool = False
    # ab wann das Verlängern geht (wenn noch zu früh)
    opens_at: datetime | None = None
    reason: str | None = None


class Renewed(BaseModel):
    filename: str
    password: str
    p12_base64: str
    not_after: datetime


def renew_url(base: str, db) -> str | None:
    return base.rstrip("/") + PATH if get_general(db)["device_self_renew"] else None


def _device(request: Request, db) -> Device | None:
    fp = client_fingerprint(request)
    if not fp:
        return None
    return db.scalar(select(Device).where(Device.fingerprint == fp))


def _old_intermediate(db, device: Device) -> bool:
    """Stammt das Zertifikat noch vom alten Zwischenzertifikat (CA-Wechsel)?"""
    active = active_authority(db, "intermediate")
    if active is None:
        return False
    from tesseract.identity import _aki, _ski

    aki, ski = _aki(pki.load_cert(device.cert_pem)), _ski(pki.load_cert(active.cert_pem))
    return aki is not None and ski is not None and aki != ski


def _check(db, device: Device | None) -> RenewStatus:
    g = get_general(db)
    out = RenewStatus(enabled=bool(g["device_self_renew"]), recognized=device is not None)
    if not out.enabled:
        out.reason = "Selbst verlängern ist ausgeschaltet – bitte an den Admin wenden."
        return out
    if device is None:
        out.reason = (
            "Kein Gerätezertifikat erkannt. Öffne den Link auf dem Gerät, das verlängert werden "
            "soll, und wähle dort das Tesseract-Zertifikat aus."
        )
        return out
    now = utcnow()
    out.device, out.person = device.name, device.person.name
    out.not_after = device.not_after
    out.days_left = max(0, int((device.not_after - now).total_seconds() // 86400))
    if device.revoked_at is not None or device.not_after <= now:
        out.reason = "Dieses Gerät ist gesperrt oder abgelaufen – bitte an den Admin wenden."
        return out
    if device.person.disabled:
        out.reason = "Der Zugang ist gesperrt – bitte an den Admin wenden."
        return out
    window = int(g["device_self_renew_days"])
    opens = device.not_after - timedelta(days=window)
    if now < opens and not _old_intermediate(db, device):
        out.opens_at = opens
        out.reason = f"Verlängern geht ab {window} Tage vor Ablauf."
        return out
    out.can_renew = True
    return out


@public.get("")
def renew_status(request: Request, db: DB) -> RenewStatus:
    return _check(db, _device(request, db))


@public.post("")
def renew_self(request: Request, db: DB, box: Box, settings: AppSettings) -> Renewed:
    """Neues Zertifikat für dieses Gerät – genau einmal, das alte gilt sofort nicht mehr."""
    device = _device(request, db)
    check = _check(db, device)
    if not check.can_renew or device is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, check.reason or "Nicht möglich")
    days = None if device.unlimited else DEFAULT_DEVICE_DAYS
    try:
        issued = renew_device(db, box, device, days)
    except CAError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    audit.record(
        db,
        actor=device.person.name,
        action="device_renewed",
        target=f"{device.person.name} · {device.name}",
        details={
            "serial": device.serial,
            "not_after": device.not_after.isoformat(),
            "via": "selbst",
        },
        ip=client_ip(request),
    )
    db.commit()
    # neuer Fingerabdruck → Freigabelisten der Hosts neu übertragen
    apply_all(db, settings, request.app.state.caddy_transport)
    db.commit()
    return Renewed(
        filename=issued.filename,
        password=issued.password,
        p12_base64=base64.b64encode(issued.p12).decode(),
        not_after=device.not_after,
    )
