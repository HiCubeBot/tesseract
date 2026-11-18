from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from tesseract.caddy.config import custom_tag
from tests.conftest import FakeCaddy


def _pem(names: list[str]) -> tuple[str, str, str]:
    """(Zertifikat, Schlüssel, anderer Schlüssel)"""
    key = ec.generate_private_key(ec.SECP256R1())
    other = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Firma GmbH")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=90))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in names]), False)
        .sign(key, hashes.SHA256())
    )

    def k(x):
        return x.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ).decode()

    return cert.public_bytes(serialization.Encoding.PEM).decode(), k(key), k(other)


def test_upload_assign_and_config(auth_client: TestClient, caddy: FakeCaddy) -> None:
    crt, key, other = _pem(["intranet.firma.de"])
    r = auth_client.post(
        "/api/custom-certs", json={"name": "Firma", "certificate": crt, "key": other}
    )
    assert r.status_code == 422 and "passt nicht" in r.json()["detail"]
    r = auth_client.post(
        "/api/custom-certs", json={"name": "Firma", "certificate": "x", "key": key}
    )
    assert r.status_code == 422
    r = auth_client.post(
        "/api/custom-certs", json={"name": "Firma", "certificate": crt, "key": key}
    )
    assert r.status_code == 201, r.text
    cert = r.json()
    assert cert["names"] == ["intranet.firma.de"] and "Firma GmbH" in cert["issuer"]
    assert "key" not in cert

    host = auth_client.post(
        "/api/hosts",
        json={
            "domain": "intranet.firma.de",
            "node_id": 1,
            "upstream_host": "10.0.0.9",
            "upstream_port": 80,
            "custom_cert_id": cert["id"],
        },
    ).json()["host"]
    assert host["custom_cert_id"] == cert["id"]

    tls = caddy.last["apps"]["tls"]
    loaded = tls["certificates"]["load_pem"][0]
    assert loaded["tags"] == [custom_tag(cert["id"])] and "PRIVATE KEY" in loaded["key"]
    server = caddy.last["apps"]["http"]["servers"]["https"]
    assert "intranet.firma.de" in server["automatic_https"]["skip_certificates"]
    policy = next(
        p
        for p in server["tls_connection_policies"]
        if p.get("match", {}).get("sni") == ["intranet.firma.de"]
    )
    assert policy["certificate_selection"] == {"any_tag": [custom_tag(cert["id"])]}
    # Anzeige ohne Schlüssel
    assert "PRIVATE KEY" not in auth_client.get("/api/nodes/1/config").text

    # Benutzt → nicht löschbar; im Verlauf mit Namen
    assert auth_client.delete(f"/api/custom-certs/{cert['id']}").status_code == 409
    v = auth_client.get(f"/api/hosts/{host['id']}/versions").json()[0]
    assert v["snapshot"]["custom_cert"] == "Firma"


def test_replace(auth_client: TestClient, caddy: FakeCaddy) -> None:
    crt, key, _ = _pem(["a.firma.de"])
    c = auth_client.post(
        "/api/custom-certs", json={"name": "A", "certificate": crt, "key": key}
    ).json()
    crt2, key2, _ = _pem(["a.firma.de", "b.firma.de"])
    r = auth_client.put(
        f"/api/custom-certs/{c['id']}", json={"name": "A", "certificate": crt2, "key": key2}
    )
    assert r.json()["names"] == ["a.firma.de", "b.firma.de"]
    assert r.json()["fingerprint"] != c["fingerprint"]
    assert auth_client.delete(f"/api/custom-certs/{c['id']}").status_code == 204
