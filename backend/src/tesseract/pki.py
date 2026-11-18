"""Eigene PKI: Root-CA (offline), Geräte-Zwischenzertifikat, Client-Zertifikate.

- Root:          ECDSA P-384, 10 Jahre, signiert nur Zwischenzertifikate (pathlen 0 darunter)
- Zwischenzert.: ECDSA P-384, 3 Jahre, signiert Geräte-, Admin- und später Node-Zertifikate
- Gerät:         ECDSA P-256, EKU clientAuth – P-256 wird von allen Plattformen unterstützt
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

ROOT_YEARS = 10
INTERMEDIATE_YEARS = 3
BACKDATE = timedelta(minutes=5)  # gegen leicht falsch gehende Uhren


@dataclass
class KeyPair:
    key: ec.EllipticCurvePrivateKey
    cert: x509.Certificate


def _name(cn: str, org: str = "Tesseract") -> x509.Name:
    return x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
        ]
    )


def _ski(key: ec.EllipticCurvePrivateKey) -> x509.SubjectKeyIdentifier:
    return x509.SubjectKeyIdentifier.from_public_key(key.public_key())


def _ca_usage() -> x509.KeyUsage:
    return x509.KeyUsage(
        digital_signature=True,
        content_commitment=False,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=True,
        crl_sign=True,
        encipher_only=False,
        decipher_only=False,
    )


def generate_root(cn: str = "Tesseract Root CA", now: datetime | None = None) -> KeyPair:
    now = now or datetime.now(UTC)
    key = ec.generate_private_key(ec.SECP384R1())
    name = _name(cn)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - BACKDATE)
        .not_valid_after(now + timedelta(days=365 * ROOT_YEARS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .add_extension(_ca_usage(), critical=True)
        .add_extension(_ski(key), critical=False)
        .sign(key, hashes.SHA384())
    )
    return KeyPair(key, cert)


def generate_intermediate(
    root: KeyPair, cn: str = "Tesseract Geräte-CA", now: datetime | None = None
) -> KeyPair:
    now = now or datetime.now(UTC)
    key = ec.generate_private_key(ec.SECP384R1())
    not_after = min(now + timedelta(days=365 * INTERMEDIATE_YEARS), root.cert.not_valid_after_utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(cn))
        .issuer_name(root.cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - BACKDATE)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(_ca_usage(), critical=True)
        .add_extension(_ski(key), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(root.key.public_key()),
            critical=False,
        )
        .sign(root.key, hashes.SHA384())
    )
    return KeyPair(key, cert)


def issue_client(
    issuer: KeyPair,
    *,
    cn: str,
    org_unit: str = "",
    not_after: datetime,
    now: datetime | None = None,
) -> KeyPair:
    now = now or datetime.now(UTC)
    not_after = min(not_after, issuer.cert.not_valid_after_utc)
    attrs = [x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Tesseract")]
    if org_unit:
        attrs.append(x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, org_unit[:64]))
    attrs.append(x509.NameAttribute(NameOID.COMMON_NAME, cn[:64]))
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name(attrs))
        .issuer_name(issuer.cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - BACKDATE)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .add_extension(_ski(key), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer.key.public_key()),
            critical=False,
        )
        .sign(issuer.key, hashes.SHA256())
    )
    return KeyPair(key, cert)


# ---------- Formate ----------


def cert_pem(cert: x509.Certificate) -> str:
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def load_cert(pem: str) -> x509.Certificate:
    return x509.load_pem_x509_certificate(pem.encode())


def key_pem(key: ec.EllipticCurvePrivateKey, passphrase: str | None = None) -> str:
    enc = (
        serialization.BestAvailableEncryption(passphrase.encode())
        if passphrase
        else serialization.NoEncryption()
    )
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, enc
    ).decode()


def load_key(pem: str | bytes, passphrase: str | None = None) -> ec.EllipticCurvePrivateKey:
    data = pem.encode() if isinstance(pem, str) else pem
    key = serialization.load_pem_private_key(data, passphrase.encode() if passphrase else None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise ValueError("Nur ECDSA-Schlüssel werden unterstützt")
    return key


def fingerprint(cert: x509.Certificate) -> str:
    """SHA-256 über DER, kleingeschrieben hex – wie Caddys {http.request.tls.client.fingerprint}."""
    return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def format_fingerprint(fp: str) -> str:
    return ":".join(fp[i : i + 2] for i in range(0, len(fp), 2)).upper()


def serial_hex(cert: x509.Certificate) -> str:
    return format(cert.serial_number, "x")


def der_b64(cert: x509.Certificate) -> str:
    import base64

    return base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode()


def generate_p12_password() -> str:
    # Gut abzutippen (z. B. am Handy): Gruppen aus Kleinbuchstaben und Ziffern
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4))


def to_p12(device: KeyPair, chain: list[x509.Certificate], password: str, name: str) -> bytes:
    """PKCS#12 mit 3DES/SHA1 – das importieren auch ältere iOS-, macOS- und Android-Versionen."""
    encryption = (
        serialization.PrivateFormat.PKCS12.encryption_builder()
        .kdf_rounds(50000)
        .key_cert_algorithm(pkcs12.PBES.PBESv1SHA1And3KeyTripleDESCBC)
        .hmac_hash(hashes.SHA1())
        .build(password.encode())
    )
    return pkcs12.serialize_key_and_certificates(
        name.encode(), device.key, device.cert, chain, encryption
    )
