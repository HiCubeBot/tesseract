"""CA einrichten, Geräte-Zertifikate ausstellen und sperren."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tesseract import pki
from tesseract.db.models import Authority, Device, Node, Person, utcnow
from tesseract.secretbox import SecretBox

KEY_CONTEXT = "authority-key"
# .p12 der Geräte und ihr Passwort (zum späteren Abruf)
P12_CONTEXT = "device-p12"
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


def trusted_intermediates(db: Session) -> list[Authority]:
    """Aktives Zwischenzertifikat zuerst, dann ältere, die noch gültig sind und an denen noch
    aktive Geräte oder Nodes hängen."""
    now = utcnow()
    out = []
    for a in db.scalars(
        select(Authority)
        .where(Authority.kind == "intermediate", Authority.not_after > now)
        .order_by(Authority.active.desc(), Authority.id.desc())
    ):
        if a.active or devices_of(db, a, active_only=True) or nodes_of(db, a):
            out.append(a)
    return out


def _aki(cert) -> bytes | None:
    from cryptography import x509

    try:
        return cert.extensions.get_extension_for_class(
            x509.AuthorityKeyIdentifier
        ).value.key_identifier
    except x509.ExtensionNotFound:
        return None


def _ski(cert) -> bytes | None:
    from cryptography import x509

    try:
        return cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest
    except x509.ExtensionNotFound:
        # importierte CA ohne SKI: so, wie pki.authority_key_id die AKI dann bildet
        return x509.SubjectKeyIdentifier.from_public_key(cert.public_key()).digest


def issued_by(cert_pem: str, authority: Authority) -> bool:
    """Stammt das Zertifikat von diesem Zwischenzertifikat (über die Schlüssel-ID)?"""
    aki = _aki(pki.load_cert(cert_pem))
    return aki is not None and aki == _ski(pki.load_cert(authority.cert_pem))


def nodes_of(db: Session, authority: Authority) -> list[Node]:
    """Nodes, deren gültiges Zertifikat von diesem Zwischenzertifikat stammt."""
    now = utcnow()
    return [
        n
        for n in db.scalars(select(Node).where(Node.cert_pem.is_not(None)))
        if n.cert_not_after and _as_utc(n.cert_not_after) > now and issued_by(n.cert_pem, authority)
    ]


def _as_utc(dt: datetime) -> datetime:
    from datetime import UTC

    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def node_cert_outdated(db: Session, node: Node) -> bool:
    """Node-Zertifikat stammt nicht vom aktiven Zwischenzertifikat (nach einem CA-Wechsel) –
    der Agent soll es gleich erneuern statt erst kurz vor Ablauf."""
    active = active_authority(db, "intermediate")
    return bool(active and node.cert_pem and not issued_by(node.cert_pem, active))


def devices_of(db: Session, authority: Authority, active_only: bool = False) -> list[Device]:
    """Geräte, die von diesem Zwischenzertifikat ausgestellt wurden (über die Schlüssel-ID)."""
    ski = _ski(pki.load_cert(authority.cert_pem))
    stmt = select(Device)
    if active_only:
        stmt = stmt.where(Device.revoked_at.is_(None), Device.not_after > utcnow())
    return [d for d in db.scalars(stmt) if _aki(pki.load_cert(d.cert_pem)) == ski]


def rotate_intermediate(
    db: Session, box: SecretBox, root_key_pem: str, passphrase: str
) -> Authority:
    """Neues Zwischenzertifikat mit dem (offline aufbewahrten) Root-Schlüssel. Der Schlüssel
    wird nur für diesen Vorgang entschlüsselt und nicht gespeichert. Das alte bleibt vertraut,
    solange noch Geräte daran hängen – sie lassen sich nach und nach verlängern."""
    root = active_authority(db, "root")
    old = active_authority(db, "intermediate")
    if root is None or old is None:
        raise CAError("Die Zertifizierungsstelle ist noch nicht eingerichtet")
    try:
        key = pki.load_key(root_key_pem.strip().encode(), passphrase or None)
    except (ValueError, TypeError) as e:
        raise CAError("Root-Schlüssel oder Passphrase falsch") from e
    root_cert = pki.load_cert(root.cert_pem)
    if not pki.same_key(key, root_cert):
        raise CAError("Dieser Schlüssel gehört nicht zum Root-Zertifikat dieser CA")
    inter = pki.generate_intermediate(pki.KeyPair(key, root_cert))
    old.active = False
    new = _authority(
        inter, "intermediate", box.encrypt(pki.key_pem(inter.key).encode(), KEY_CONTEXT)
    )
    db.add(new)
    db.flush()
    return new


# ---------- Bestehende CA importieren, Root wechseln ----------


def _parse_cert(pem: str, what: str):
    from cryptography import x509

    try:
        cert = pki.load_cert(pem.strip())
    except ValueError as e:
        raise CAError(f"{what}: kein gültiges PEM-Zertifikat") from e
    try:
        bc = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
    except x509.ExtensionNotFound:
        bc = None
    if bc is None or not bc.ca:
        raise CAError(f"{what} ist kein CA-Zertifikat (BasicConstraints CA fehlt)")
    try:
        ku = cert.extensions.get_extension_for_class(x509.KeyUsage).value
        if not ku.key_cert_sign:
            raise CAError(f"{what} darf keine Zertifikate signieren (KeyUsage keyCertSign fehlt)")
    except x509.ExtensionNotFound:
        pass
    now = utcnow()
    if cert.not_valid_after_utc <= now + timedelta(days=1):
        raise CAError(f"{what} ist abgelaufen")
    if cert.not_valid_before_utc > now + timedelta(minutes=10):
        raise CAError(f"{what} ist noch nicht gültig")
    return cert


def _parse_key(pem: str, passphrase: str, cert, what: str):
    try:
        key = pki.load_key(pem.strip().encode(), passphrase or None)
    except TypeError as e:
        # verschlüsselt, aber keine Passphrase – oder umgekehrt
        msg = "Passphrase fehlt" if not passphrase else "Schlüssel ist nicht verschlüsselt"
        raise CAError(f"{what}: {msg}") from e
    except ValueError as e:
        detail = str(e) if "Bit" in str(e) or "unterstützt" in str(e) else "Passphrase falsch?"
        raise CAError(f"{what}: Schlüssel nicht lesbar – {detail}") from e
    if not pki.same_key(key, cert):
        raise CAError(f"{what}: Schlüssel gehört nicht zum Zertifikat")
    return key


def _fingerprint_free(db: Session, cert, what: str) -> None:
    fp = pki.fingerprint(cert)
    if db.scalar(select(Authority.id).where(Authority.fingerprint == fp)):
        raise CAError(f"{what} ist hier bereits bekannt")


def install_ca(
    db: Session,
    box: SecretBox,
    *,
    root_cert_pem: str,
    root_key_pem: str = "",
    passphrase: str = "",
    intermediate_cert_pem: str = "",
    intermediate_key_pem: str = "",
    intermediate_passphrase: str = "",
    replace: bool = False,
) -> Authority:
    """Bestehende CA übernehmen – erstmals (`replace=False`) oder als Wechsel der Root
    (`replace=True`). Zwei Wege:

    - Root-Zertifikat + Root-Schlüssel: Tesseract erzeugt daraus sein Zwischenzertifikat und
      vergisst den Root-Schlüssel sofort wieder.
    - Root-Zertifikat + fertiges Zwischenzertifikat mit Schlüssel (der Root-Schlüssel bleibt
      in der vorhandenen PKI). Ein späterer Wechsel geht dann wieder über einen Import.

    Beim Wechsel bleibt das alte Zwischenzertifikat vertraut, solange Geräte oder Nodes daran
    hängen. Gibt das neue, aktive Zwischenzertifikat zurück."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.x509 import BasicConstraints

    old_root = active_authority(db, "root")
    old_inter = active_authority(db, "intermediate")
    if replace and old_inter is None:
        raise CAError("Die Zertifizierungsstelle ist noch nicht eingerichtet")
    if not replace and old_inter is not None:
        raise CAError("Die Zertifizierungsstelle ist bereits eingerichtet")

    root_cert = _parse_cert(root_cert_pem, "Root-Zertifikat")
    same_root = old_root is not None and old_root.fingerprint == pki.fingerprint(root_cert)
    if not same_root:
        _fingerprint_free(db, root_cert, "Dieses Root-Zertifikat")

    if intermediate_cert_pem.strip():
        if not intermediate_key_pem.strip():
            raise CAError("Zum Zwischenzertifikat fehlt der Schlüssel")
        inter_cert = _parse_cert(intermediate_cert_pem, "Zwischenzertifikat")
        try:
            inter_cert.verify_directly_issued_by(root_cert)
        except (ValueError, TypeError, InvalidSignature) as e:
            raise CAError("Das Zwischenzertifikat ist nicht von diesem Root ausgestellt") from e
        _fingerprint_free(db, inter_cert, "Dieses Zwischenzertifikat")
        inter_key = _parse_key(
            intermediate_key_pem, intermediate_passphrase, inter_cert, "Zwischenzertifikat"
        )
        inter = pki.KeyPair(inter_key, inter_cert)
    else:
        if not root_key_pem.strip():
            raise CAError("Root-Schlüssel oder ein Zwischenzertifikat mit Schlüssel wird gebraucht")
        if same_root and not replace:
            raise CAError("Die Zertifizierungsstelle ist bereits eingerichtet")
        root_key = _parse_key(root_key_pem, passphrase, root_cert, "Root-Zertifikat")
        bc = root_cert.extensions.get_extension_for_class(BasicConstraints).value
        if bc.path_length is not None and bc.path_length < 1:
            raise CAError(
                "Dieses Root-Zertifikat darf keine Zwischenzertifikate ausstellen (pathlen 0) – "
                "stattdessen ein Zwischenzertifikat mit Schlüssel importieren"
            )
        inter = pki.generate_intermediate(pki.KeyPair(root_key, root_cert))

    if old_inter is not None:
        old_inter.active = False
    if not same_root:
        if old_root is not None:
            old_root.active = False
        db.add(
            Authority(
                kind="root",
                cert_pem=pki.cert_pem(root_cert),
                key_enc=None,
                fingerprint=pki.fingerprint(root_cert),
                not_before=root_cert.not_valid_before_utc,
                not_after=root_cert.not_valid_after_utc,
            )
        )
    new = _authority(
        inter, "intermediate", box.encrypt(pki.key_pem(inter.key).encode(), KEY_CONTEXT)
    )
    db.add(new)
    db.flush()
    return new


def rotate_root(db: Session, box: SecretBox, passphrase: str) -> "SetupResult":
    """Neue Root-CA samt Zwischenzertifikat erzeugen (wie bei der Einrichtung). Die alte Root
    wird abgelöst; ihr Zwischenzertifikat bleibt vertraut, solange Geräte oder Nodes daran
    hängen."""
    old_root = active_authority(db, "root")
    old_inter = active_authority(db, "intermediate")
    if old_inter is None:
        raise CAError("Die Zertifizierungsstelle ist noch nicht eingerichtet")
    if len(passphrase) < MIN_ROOT_PASSPHRASE:
        raise CAError(f"Die Passphrase braucht mindestens {MIN_ROOT_PASSPHRASE} Zeichen")
    root = pki.generate_root()
    inter = pki.generate_intermediate(root)
    old_inter.active = False
    if old_root is not None:
        old_root.active = False
    db.add(_authority(root, "root", None))
    db.add(
        _authority(inter, "intermediate", box.encrypt(pki.key_pem(inter.key).encode(), KEY_CONTEXT))
    )
    db.flush()
    return SetupResult(pki.cert_pem(root.cert), pki.key_pem(root.key, passphrase))


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
    _keep_p12(db, box, device, p12, password)
    return IssuedDevice(device, p12, password, p12_filename(device, person))


def p12_filename(device: Device, person: Person | None = None) -> str:
    person = person or device.person
    return f"tesseract-{_slug(person.name)}-{_slug(device.name)}.p12"


def _keep_p12(db: Session, box: SecretBox, device: Device, p12: bytes, password: str) -> None:
    """.p12 und Passwort verschlüsselt ablegen – wenn in den Einstellungen gewünscht."""
    from tesseract.services import get_general

    if get_general(db)["device_keep_p12"]:
        device.p12_enc = box.encrypt(p12, P12_CONTEXT)
        device.p12_password_enc = box.encrypt(password.encode(), P12_CONTEXT)
    else:
        device.p12_enc = None
        device.p12_password_enc = None


def renew_device(
    db: Session, box: SecretBox, device: Device, days: int | None = DEFAULT_DEVICE_DAYS
) -> IssuedDevice:
    """Neues Zertifikat für dasselbe Gerät (neuer Schlüssel, aktuelles Zwischenzertifikat).
    Freigaben bleiben, das alte Zertifikat gilt ab sofort nicht mehr."""
    if device.revoked_at is not None:
        raise CAError("Gesperrte Geräte lassen sich nicht verlängern")
    person = device.person
    if person.disabled:
        raise CAError(f"{person.name} ist gesperrt")
    issuer = intermediate_keypair(db, box)
    now = utcnow()
    not_after = issuer.cert.not_valid_after_utc if days is None else now + timedelta(days=days)
    kp = pki.issue_client(
        issuer, cn=device.name, org_unit=person.name, not_after=not_after, now=now
    )
    device.serial = pki.serial_hex(kp.cert)
    device.fingerprint = pki.fingerprint(kp.cert)
    device.cert_pem = pki.cert_pem(kp.cert)
    device.not_before = kp.cert.not_valid_before_utc
    device.not_after = kp.cert.not_valid_after_utc
    device.unlimited = days is None
    password = pki.generate_p12_password()
    p12 = pki.to_p12(kp, chain(db), password, f"{person.name} – {device.name}")
    _keep_p12(db, box, device, p12, password)
    return IssuedDevice(device, p12, password, p12_filename(device))


def revoke_device(device: Device, reason: str = "", at: datetime | None = None) -> None:
    if device.revoked_at is None:
        device.revoked_at = at or utcnow()
        device.revoke_reason = reason
    # gesperrt → hinterlegte Kopie ist wertlos, weg damit
    device.p12_enc = None
    device.p12_password_enc = None
