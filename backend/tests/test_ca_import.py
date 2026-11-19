"""Bestehende CA importieren und Root-CA wechseln."""

from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from tesseract import pki
from tesseract.db.models import Device
from tests.conftest import FakeCaddy
from tests.test_ca_rotation import PASS, _device, _setup, _trusted
from tests.test_nodes_agent import Agent, _csr, _new_node


def _rsa_root(path_length: int | None = None, ski: bool = True) -> pki.KeyPair:
    """Fremde Root wie aus einer vorhandenen PKI: RSA, wahlweise ohne SKI."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Firma Root CA")])
    now = datetime.now(UTC)
    b = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=path_length), critical=True)
    )
    if ski:
        b = b.add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
    return pki.KeyPair(key, b.sign(key, hashes.SHA256()))


def _rsa_intermediate(root: pki.KeyPair) -> pki.KeyPair:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Firma Geräte-CA")]))
        .issuer_name(root.cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=700))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(root.key, hashes.SHA256())
    )
    return pki.KeyPair(key, cert)


def _pem(kp: pki.KeyPair, passphrase: str | None = None) -> tuple[str, str]:
    return pki.cert_pem(kp.cert), pki.key_pem(kp.key, passphrase)


def test_import_root_with_key(auth_client: TestClient, caddy: FakeCaddy) -> None:
    root = _rsa_root(ski=False)
    cert_pem, key_pem = _pem(root, PASS)
    bad = auth_client.post(
        "/api/ca/import",
        json={"root_cert_pem": cert_pem, "root_key_pem": key_pem, "passphrase": "falsch"},
    )
    assert bad.status_code == 409 and "Schlüssel nicht lesbar" in bad.json()["detail"]
    other = pki.key_pem(_rsa_root().key)
    bad = auth_client.post(
        "/api/ca/import", json={"root_cert_pem": cert_pem, "root_key_pem": other}
    )
    assert bad.status_code == 409 and "gehört nicht" in bad.json()["detail"]

    r = auth_client.post(
        "/api/ca/import",
        json={"root_cert_pem": cert_pem, "root_key_pem": key_pem, "passphrase": PASS},
    )
    assert r.status_code == 200, r.text
    st = r.json()
    assert st["configured"] and st["root"]["subject"] == "Firma Root CA"
    assert st["root"]["key_on_controller"] is False
    assert st["intermediate"]["key_on_controller"] is True
    assert len(_trusted(caddy)) == 1

    # Geräte bekommen ihr Zertifikat vom neuen Zwischenzertifikat, das an der Firmen-Root hängt
    dev = _device(auth_client)["device"]
    db = auth_client.app.state.db.sessionmaker()
    leaf = pki.load_cert(db.get(Device, dev["id"]).cert_pem)
    db.close()
    assert leaf.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "Tesseract Geräte-CA"
    assert auth_client.get("/api/ca").json()["intermediate"]["subject"] == "Tesseract Geräte-CA"
    # nur einmal einrichten
    again = auth_client.post(
        "/api/ca/import",
        json={"root_cert_pem": cert_pem, "root_key_pem": key_pem, "passphrase": PASS},
    )
    assert again.status_code == 409
    actions = [e["action"] for e in auth_client.get("/api/audit").json()]
    assert "ca_imported" in actions


def test_import_intermediate_keeps_root_key_outside(auth_client: TestClient) -> None:
    root = _rsa_root()
    inter = _rsa_intermediate(root)
    ic, ik = _pem(inter)
    foreign = _rsa_intermediate(_rsa_root())
    r = auth_client.post(
        "/api/ca/import",
        json={
            "root_cert_pem": pki.cert_pem(root.cert),
            "intermediate_cert_pem": pki.cert_pem(foreign.cert),
            "intermediate_key_pem": pki.key_pem(foreign.key),
        },
    )
    assert r.status_code == 409 and "nicht von diesem Root" in r.json()["detail"]
    r = auth_client.post(
        "/api/ca/import",
        json={
            "root_cert_pem": pki.cert_pem(root.cert),
            "intermediate_cert_pem": ic,
            "intermediate_key_pem": ik,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["intermediate"]["subject"] == "Firma Geräte-CA"
    # RSA-Zwischenzertifikat ohne SKI stellt Geräte aus; der alte Stand bleibt zuordenbar
    created = _device(auth_client)
    assert created["password"]


def test_import_rejects_non_ca_and_pathlen_zero(auth_client: TestClient) -> None:
    root = _rsa_root(path_length=0)
    r = auth_client.post(
        "/api/ca/import",
        json={"root_cert_pem": pki.cert_pem(root.cert), "root_key_pem": pki.key_pem(root.key)},
    )
    assert r.status_code == 409 and "pathlen 0" in r.json()["detail"]

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "kein CA")])
    now = datetime.now(UTC)
    leaf = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=10))
        .sign(key, hashes.SHA256())
    )
    pem = leaf.public_bytes(serialization.Encoding.PEM).decode()
    r = auth_client.post(
        "/api/ca/import", json={"root_cert_pem": pem, "root_key_pem": pki.key_pem(key)}
    )
    assert r.status_code == 409 and "kein CA-Zertifikat" in r.json()["detail"]


def test_rotate_root_generate(auth_client: TestClient, caddy: FakeCaddy) -> None:
    _setup(auth_client)
    _device(auth_client)
    # ein Node mit Zertifikat der alten CA
    created = _new_node(auth_client)
    agent = Agent(auth_client, created["join"]["token"])
    node_id = created["node"]["id"]
    assert auth_client.post(f"/api/nodes/{node_id}/approve").status_code == 200
    agent.connect()
    st = agent.post("/api/agent/status", {"agent_version": "1.4.0"}).json()
    assert st["renew_cert"] is False
    before = auth_client.get("/api/ca").json()

    short = auth_client.post("/api/ca/rotate-root", json={"mode": "generate", "passphrase": "kurz"})
    assert short.status_code == 409

    r = auth_client.post(
        "/api/ca/rotate-root", json={"mode": "generate", "passphrase": "neue-passphrase-456"}
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert "ENCRYPTED PRIVATE KEY" in out["root_key_pem"]
    pki.load_key(out["root_key_pem"], "neue-passphrase-456")
    st = out["status"]
    assert st["root"]["fingerprint"] != before["root"]["fingerprint"]
    assert st["intermediate"]["fingerprint"] != before["intermediate"]["fingerprint"]
    prev = st["previous"][0]
    assert [d["name"] for d in prev["devices"]] == ["iPhone"]
    assert [n["name"] for n in prev["nodes"]] == ["pi-eltern"]
    assert len(_trusted(caddy)) == 2

    # Agent erfährt vom Wechsel und erneuert sein Zertifikat
    st = agent.post("/api/agent/status", {"agent_version": "1.4.0"}).json()
    assert st["renew_cert"] is True
    new_key = ec.generate_private_key(ec.SECP256R1())
    renewed = agent.post("/api/agent/renew", {"csr": _csr(new_key)})
    assert renewed.status_code == 200, renewed.text
    new_root = auth_client.get("/api/ca/root.pem").text
    assert new_root.strip() in renewed.json()["chain_pem"]
    prev = auth_client.get("/api/ca").json()["previous"][0]
    assert prev["nodes"] == [] and len(prev["devices"]) == 1
    actions = [e["action"] for e in auth_client.get("/api/audit").json()]
    assert "ca_root_rotated" in actions


def test_rotate_root_import(auth_client: TestClient, caddy: FakeCaddy) -> None:
    _setup(auth_client)
    root = _rsa_root()
    cert_pem, key_pem = _pem(root)
    r = auth_client.post(
        "/api/ca/rotate-root",
        json={"mode": "import", "root_cert_pem": cert_pem, "root_key_pem": key_pem},
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["root_key_pem"] is None
    assert out["status"]["root"]["subject"] == "Firma Root CA"
    # keine Geräte am alten Zwischenzertifikat → Caddy vertraut nur dem neuen
    assert out["status"]["previous"] == [] and len(_trusted(caddy)) == 1
    # dieselbe Root noch einmal: nur neues Zwischenzertifikat (wie ein Wechsel)
    again = auth_client.post(
        "/api/ca/rotate-root",
        json={"mode": "import", "root_cert_pem": cert_pem, "root_key_pem": key_pem},
    )
    assert again.status_code == 200
    assert again.json()["status"]["root"]["fingerprint"] == out["status"]["root"]["fingerprint"]
    # der unverschlüsselte Root-Schlüssel taugt auch für den normalen Wechsel
    rot = auth_client.post("/api/ca/rotate", json={"root_key_pem": key_pem})
    assert rot.status_code == 200, rot.text
