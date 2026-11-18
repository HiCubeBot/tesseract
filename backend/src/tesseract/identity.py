"""CA einrichten, Geräte-Zertifikate ausstellen und sperren."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tesseract import pki
from tesseract.db.models import Authority, Device, Person, utcnow
from tesseract.secretbox import SecretBox

KEY_CONTEXT = "authority-key"
DEFAULT_DEVICE_DAYS = 365
MIN_ROOT_PASSPHRASE = 12


class CAError(Exception):
    pass


def active_authority(db: Session, kind: str) -> Authority | None:
    return db.scalar(
        select(Authority)
        .where(Authority.kind == kind, Authority.active)
        .order_by(Authority.id.desc())
    )


def ca_configured(db: Session) -> bool:
    return active_authority(db, "intermediate") is not None


def intermediate_keypair(db: Session, box: SecretBox) -> pki.KeyPair:
    inter = active_authority(db, "intermediate")
    if inter is None or inter.key_enc is None:
        raise CAError("Die Zertifizierungsstelle ist noch nicht eingerichtet")
    key = pki.load_key(box.decrypt(inter.key_enc, KEY_CONTEXT))
    return pki.KeyPair(key, pki.load_cert(inter.cert_pem))


def chain(db: Session) -> list:
    """Zwischenzertifikat + Root – kommt mit in jede .p12."""
    result = []
    for kind in ("intermediate", "root"):
        a = active_authority(db, kind)
        if a is not None:
            result.append(pki.load_cert(a.cert_pem))
    return result


def _authority(kp: pki.KeyPair, kind: str, key_enc: str | None) -> Authority:
    return Authority(
        kind=kind,
        cert_pem=pki.cert_pem(kp.cert),
        key_enc=key_enc,
        fingerprint=pki.fingerprint(kp.cert),
        not_before=kp.cert.not_valid_before_utc,
        not_after=kp.cert.not_valid_after_utc,
    )


@dataclass
class SetupResult:
    root_cert_pem: str
    root_key_pem: str  # mit der Passphrase verschlüsselt


def setup_ca(db: Session, box: SecretBox, passphrase: str) -> SetupResult:
    """Erzeugt Root und Zwischenzertifikat. Den Root-Schlüssel bekommt nur der Admin
    (verschlüsselt) – der Controller vergisst ihn sofort."""
    if ca_configured(db):
        raise CAError("Die Zertifizierungsstelle ist bereits eingerichtet")
    if len(passphrase) < MIN_ROOT_PASSPHRASE:
        raise CAError(f"Die Passphrase braucht mindestens {MIN_ROOT_PASSPHRASE} Zeichen")
    root = pki.generate_root()
    inter = pki.generate_intermediate(root)
    db.add(_authority(root, "root", None))
    db.add(
        _authority(inter, "intermediate", box.encrypt(pki.key_pem(inter.key).encode(), KEY_CONTEXT))
    )
    return SetupResult(pki.cert_pem(root.cert), pki.key_pem(root.key, passphrase))


# ---------- Geräte ----------


def active_device_count(db: Session, person_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Device)
            .where(
                Device.person_id == person_id,
                Device.revoked_at.is_(None),
                Device.not_after > utcnow(),
            )
        )
        or 0
    )


@dataclass
class IssuedDevice:
    device: Device
    p12: bytes
    password: str
    filename: str


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "geraet"


def issue_device(
    db: Session,
    box: SecretBox,
    person: Person,
    *,
    name: str,
    platform: str = "",
    days: int | None = DEFAULT_DEVICE_DAYS,
    check_limit: bool = True,
) -> IssuedDevice:
    """Stellt ein Zertifikat aus. `days=None` = so lange wie das Zwischenzertifikat."""
    if person.disabled:
        raise CAError(f"{person.name} ist gesperrt")
    if check_limit and active_device_count(db, person.id) >= person.max_devices:
        raise CAError(f"{person.name} hat bereits {person.max_devices} aktive Geräte")
    issuer = intermediate_keypair(db, box)
    now = utcnow()
    not_after = issuer.cert.not_valid_after_utc if days is None else now + timedelta(days=days)
    kp = pki.issue_client(issuer, cn=name, org_unit=person.name, not_after=not_after, now=now)
    device = Device(
        person_id=person.id,
        name=name,
        platform=platform,
        serial=pki.serial_hex(kp.cert),
        fingerprint=pki.fingerprint(kp.cert),
        cert_pem=pki.cert_pem(kp.cert),
        not_before=kp.cert.not_valid_before_utc,
        not_after=kp.cert.not_valid_after_utc,
        unlimited=days is None,
    )
    db.add(device)
    password = pki.generate_p12_password()
    p12 = pki.to_p12(kp, chain(db), password, f"{person.name} – {name}")
    filename = f"tesseract-{_slug(person.name)}-{_slug(name)}.p12"
    return IssuedDevice(device, p12, password, filename)


def revoke_device(device: Device, reason: str = "", at: datetime | None = None) -> None:
    if device.revoked_at is None:
        device.revoked_at = at or utcnow()
        device.revoke_reason = reason
