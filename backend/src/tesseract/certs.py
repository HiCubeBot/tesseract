"""Zertifikatsübersicht: liest die von Caddy ausgelieferten Zertifikate per TLS aus.

Caddys Admin-API kann verwaltete Zertifikate nicht auflisten. Stattdessen baut der
Controller pro Name eine TLS-Verbindung zu Caddy auf (SNI = Name) und liest das
Server-Zertifikat. Das klappt auch bei Hosts mit strengem mTLS: Bei TLS 1.3 kommt das
Server-Zertifikat an, bevor Caddy das fehlende Client-Zertifikat ablehnt.
"""

import hashlib
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID

from tesseract.db.models import utcnow

SOON = timedelta(days=21)


@dataclass
class Presented:
    """Ein ausgeliefertes Zertifikat."""

    fingerprint: str
    names: list[str]
    issuer: str
    issuer_org: str
    not_before: datetime
    not_after: datetime
    serial: str


@dataclass
class Probe:
    name: str
    cert: Presented | None = None
    error: str | None = None


def tls_address(admin_url: str, override: str = "") -> tuple[str, int]:
    if override:
        host, _, port = override.rpartition(":")
        return host.strip("[]") or override, int(port) if port.isdigit() else 443
    return urlsplit(admin_url).hostname or "127.0.0.1", 443


def _cn(name: x509.Name) -> str:
    attrs = name.get_attributes_for_oid(NameOID.COMMON_NAME)
    return str(attrs[0].value) if attrs else ""


def _org(name: x509.Name) -> str:
    attrs = name.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
    return str(attrs[0].value) if attrs else ""


def parse(der: bytes) -> Presented:
    cert = x509.load_der_x509_certificate(der)
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        names = [
            *san.get_values_for_type(x509.DNSName),
            *map(str, san.get_values_for_type(x509.IPAddress)),
        ]
    except x509.ExtensionNotFound:
        names = [_cn(cert.subject)] if _cn(cert.subject) else []
    return Presented(
        fingerprint=hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest(),
        names=names,
        issuer=_cn(cert.issuer) or cert.issuer.rfc4514_string(),
        issuer_org=_org(cert.issuer),
        not_before=cert.not_valid_before_utc,
        not_after=cert.not_valid_after_utc,
        serial=format(cert.serial_number, "x"),
    )


def probe(host: str, port: int, name: str, timeout: float = 4.0) -> Probe:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with (
            socket.create_connection((host, port), timeout=timeout) as raw,
            ctx.wrap_socket(raw, server_hostname=name) as s,
        ):
            der = s.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError) as e:
        return Probe(name, error=str(e) or type(e).__name__)
    if not der:
        return Probe(name, error="kein Zertifikat ausgeliefert")
    return Probe(name, cert=parse(der))


def probe_all(host: str, port: int, names: list[str]) -> list[Probe]:
    if not names:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(names))) as pool:
        return list(pool.map(lambda n: probe(host, port, n), names))


def issuer_label(c: Presented) -> str:
    text = f"{c.issuer_org} {c.issuer}".lower()
    if "let's encrypt" in text or c.issuer in ("R10", "R11", "R12", "R13", "E5", "E6", "E7", "E8"):
        return "Let's Encrypt"
    if "zerossl" in text:
        return "ZeroSSL"
    if "caddy local authority" in text:
        return "Caddy (lokal)"
    if "staging" in text or "fake" in text:
        return "Let's Encrypt (Staging)"
    return c.issuer_org or c.issuer or "unbekannt"


def status(c: Presented) -> str:
    now = utcnow()
    if c.not_after <= now:
        return "expired"
    # Caddys lokale CA stellt absichtlich kurzlebige Zertifikate aus und erneuert selbst
    if issuer_label(c) == "Caddy (lokal)":
        return "ok"
    if c.not_after - now < SOON:
        return "soon"
    return "ok"


def explain(error: str) -> str:
    """Technische TLS-Fehler in verständliche Sätze übersetzen."""
    e = error.lower()
    if "internal error" in e or "unrecognized name" in e:
        return "Caddy hat (noch) kein Zertifikat für diesen Namen – Abruf läuft oder scheitert"
    if "refused" in e or "timed out" in e or "unreachable" in e:
        return f"Caddy nicht erreichbar ({error})"
    return error


@dataclass
class CertificateGroup:
    cert: Presented
    hosts: list[str] = field(default_factory=list)
    wildcard: bool = False
