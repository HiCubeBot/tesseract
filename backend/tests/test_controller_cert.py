"""Client-Zertifikat des Controllers: ausstellen, erneuern, pro Host freigeben, ausgehend nutzen."""

import ssl
from datetime import timedelta

from fastapi.testclient import TestClient

from tesseract import controllercert, pki
from tesseract.caddy.config import FINGERPRINT
from tesseract.db.models import utcnow
from tests.conftest import FakeCaddy
from tests.test_mtls import HOST, _gate, _policy, _setup


def test_needs_ca(auth_client: TestClient) -> None:
    r = auth_client.post("/api/hosts", json={**HOST, "access": "mtls", "allow_controller": True})
    assert r.status_code == 409 and "Zertifizierungsstelle" in r.text


def test_host_allows_controller(auth_client: TestClient, caddy: FakeCaddy) -> None:
    ids = _setup(auth_client)
    r = auth_client.post(
        "/api/hosts",
        json={
            **HOST,
            "access": "mtls",
            "grant_group_ids": [ids["fam"]["id"]],
            "allow_controller": True,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["host"]["allow_controller"] is True
    app = auth_client.app
    with app.state.db.sessionmaker() as db:
        fp, pem = controllercert.allowed_entry(db)
    cert = pki.load_cert(pem)
    assert cert.subject.rfc4514_string().endswith("CN=Tesseract Controller") or "Controller" in (
        cert.subject.rfc4514_string()
    )
    fps = _gate(caddy, "fotos.example.org")["match"][0]["not"][0]["vars"][FINGERPRINT]
    assert fp in fps
    certs = _policy(caddy, "fotos.example.org")["verifiers"][0]["leaf_certs_loaders"][0][
        "certificates"
    ]
    assert pem in certs
    # Dateien für ausgehende Verbindungen
    d = controllercert.directory(app.state.settings)
    assert (d / "cert.pem").exists() and (d / "key.pem").exists()
    assert isinstance(controllercert.ssl_context(app.state.settings), ssl.SSLContext)
    # Benachrichtigungen nutzen es (ohne Test-Transport)
    sender = app.state.notifier.sender
    sender.transport = None
    with sender._http() as h:
        assert h is not None
    # ausschalten → nicht mehr freigegeben
    host_id = r.json()["host"]["id"]
    body = {**HOST, "access": "mtls", "grant_group_ids": [ids["fam"]["id"]]}
    auth_client.put(f"/api/hosts/{host_id}", json=body)
    fps = _gate(caddy, "fotos.example.org")["match"][0]["not"][0]["vars"][FINGERPRINT]
    assert fp not in fps


def test_renewal(auth_client: TestClient) -> None:
    _setup(auth_client)
    app = auth_client.app
    with app.state.db.sessionmaker() as db:
        box, settings = app.state.secretbox, app.state.settings
        assert controllercert.ensure(db, box, settings) is True
        first = controllercert.stored(db)["fingerprint"]
        assert controllercert.ensure(db, box, settings) is False
        # kurz vor Ablauf → neu
        later = utcnow() + timedelta(days=controllercert.VALID_DAYS - 10)
        assert controllercert.ensure(db, box, settings, now=later) is True
        assert controllercert.stored(db)["fingerprint"] != first
        db.commit()
