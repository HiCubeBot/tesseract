"""Zertifikatsübersicht – gegen einen echten kleinen TLS-Server im Test."""

import socket
import ssl
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from tesseract.certs import issuer_label, parse, probe, status


def _cert(names: list[str], issuer: str, days: int) -> tuple[bytes, bytes]:
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([]))
        .issuer_name(
            x509.Name(
                [
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Let's Encrypt"),
                    x509.NameAttribute(NameOID.COMMON_NAME, issuer),
                ]
            )
        )
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in names]), False)
        .sign(key, hashes.SHA256())
    )
    return (
        cert.public_bytes(serialization.Encoding.PEM),
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )


@pytest.fixture
def tls_server(tmp_path: Path) -> Iterator[int]:
    """TLS-Server mit zwei Zertifikaten je nach SNI (wie Caddy)."""
    contexts = {}
    for name, (names, days) in {
        "wild": (["*.home.example.org"], 60),
        "blog": (["blog.example.org"], 10),
    }.items():
        crt, key = _cert(names, "R11", days)
        (tmp_path / f"{name}.crt").write_bytes(crt)
        (tmp_path / f"{name}.key").write_bytes(key)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(tmp_path / f"{name}.crt", tmp_path / f"{name}.key")
        contexts[name] = ctx
    default = contexts["wild"]

    def pick(sock, server_name, _ctx):
        sock.context = contexts["blog"] if server_name == "blog.example.org" else default

    default.sni_callback = pick
    srv = socket.create_server(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    stop = threading.Event()

    def serve() -> None:
        srv.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except TimeoutError:
                continue
            try:
                with default.wrap_socket(conn, server_side=True):
                    pass
            except (ssl.SSLError, OSError):
                pass

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    yield port
    stop.set()
    t.join(2)
    srv.close()


def test_parse_and_labels() -> None:
    crt, _ = _cert(["a.example.org"], "R11", 5)
    c = parse(x509.load_pem_x509_certificate(crt).public_bytes(serialization.Encoding.DER))
    assert c.names == ["a.example.org"]
    assert issuer_label(c) == "Let's Encrypt"
    assert status(c) == "soon"


def test_probe(tls_server: int) -> None:
    p = probe("127.0.0.1", tls_server, "grafana.home.example.org")
    assert p.cert is not None and p.cert.names == ["*.home.example.org"]
    assert probe("127.0.0.1", 1, "x.example.org").error


def test_overview(auth_client: TestClient, tls_server: int, settings) -> None:
    settings.caddy_tls_address = f"127.0.0.1:{tls_server}"
    for domain in ("grafana.home.example.org", "nas.home.example.org", "blog.example.org"):
        auth_client.post(
            "/api/hosts",
            json={"domain": domain, "node_id": 1, "upstream_host": "10.0.0.1", "upstream_port": 80},
        )
    data = auth_client.get("/api/certificates?refresh=true").json()
    by_name = {tuple(c["names"]): c for c in data["certificates"]}
    wild = by_name[("*.home.example.org",)]
    blog = by_name[("blog.example.org",)]
    assert sorted(wild["hosts"]) == [
        "grafana.home.example.org",
        "nas.home.example.org",
        "tesseract.example.org",  # die Oberfläche bekommt im Test denselben Fallback
    ]
    assert wild["source"] == "wildcard" and wild["issuer"] == "Let's Encrypt"
    assert blog["status"] == "soon" and blog["hosts"] == ["blog.example.org"]
    assert blog["source"] == "http-01"
    # Sortiert nach Ablauf: was zuerst abläuft, steht oben
    assert data["certificates"][0]["names"] == ["blog.example.org"]
