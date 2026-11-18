import base64
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID

from tesseract import pki
from tesseract.secretbox import SecretBox


def test_chain_and_client_cert() -> None:
    root = pki.generate_root()
    inter = pki.generate_intermediate(root)
    now = datetime.now(UTC)
    dev = pki.issue_client(
        inter, cn="Annas iPhone", org_unit="Anna", not_after=now + timedelta(days=365)
    )

    # Signaturen und Ketten-Beziehungen
    dev.cert.verify_directly_issued_by(inter.cert)
    inter.cert.verify_directly_issued_by(root.cert)
    assert inter.cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    eku = dev.cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert ExtendedKeyUsageOID.CLIENT_AUTH in eku

    # Gerät kann nicht länger gelten als das Zwischenzertifikat
    long = pki.issue_client(inter, cn="x", not_after=now + timedelta(days=365 * 20))
    assert long.cert.not_valid_after_utc == inter.cert.not_valid_after_utc


def test_p12_roundtrip() -> None:
    root = pki.generate_root()
    inter = pki.generate_intermediate(root)
    dev = pki.issue_client(inter, cn="Laptop", not_after=datetime.now(UTC) + timedelta(days=1))
    password = pki.generate_p12_password()
    data = pki.to_p12(dev, [inter.cert, root.cert], password, "Anna – Laptop")
    key, cert, extra = pkcs12.load_key_and_certificates(data, password.encode())
    assert cert == dev.cert
    assert [c.subject for c in extra] == [inter.cert.subject, root.cert.subject]
    with pytest.raises(ValueError):
        pkcs12.load_key_and_certificates(data, b"falsch")


def test_root_key_export_is_encrypted() -> None:
    root = pki.generate_root()
    pem = pki.key_pem(root.key, "eine lange passphrase")
    assert "ENCRYPTED" in pem
    assert pki.load_key(pem, "eine lange passphrase").public_key() == root.key.public_key()


def test_secretbox() -> None:
    box = SecretBox(b"k" * 32)
    token = box.encrypt(b"geheim", "ctx")
    assert box.decrypt(token, "ctx") == b"geheim"
    with pytest.raises(InvalidTag):
        box.decrypt(token, "anderer-kontext")
    with pytest.raises(InvalidTag):
        SecretBox(b"x" * 32).decrypt(token, "ctx")


def test_fingerprint_format() -> None:
    root = pki.generate_root()
    fp = pki.fingerprint(root.cert)
    assert len(fp) == 64 and fp == fp.lower()
    assert pki.format_fingerprint(fp).count(":") == 31
    assert base64.b64decode(pki.der_b64(root.cert))
