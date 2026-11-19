"""Gäste verlängern ihr Gerät selbst – Ausweis ist das noch gültige Gerätezertifikat."""

import base64
from datetime import timedelta

from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi.testclient import TestClient

from tesseract.caddy.config import CONTROLLER_PUBLIC_PATHS, FINGERPRINT_HEADER
from tesseract.db.models import Device, utcnow
from tests.conftest import FakeCaddy
from tests.test_ca_rotation import PASS, _device, _setup


def _fp(dev: dict) -> str:
    return dev["fingerprint"].replace(":", "").lower()


def _expire_in(client: TestClient, device_id: int, days: int) -> None:
    with client.app.state.db.sessionmaker() as db:
        d = db.get(Device, device_id)
        d.not_after = utcnow() + timedelta(days=days)
        db.commit()


def test_status_without_certificate(auth_client: TestClient) -> None:
    _setup(auth_client)
    st = auth_client.get("/api/renew").json()
    assert st["enabled"] and not st["recognized"] and not st["can_renew"]
    assert "Kein Gerätezertifikat" in st["reason"]
    assert auth_client.post("/api/renew").status_code == 403


def test_renew_in_window(auth_client: TestClient, caddy: FakeCaddy) -> None:
    _setup(auth_client)
    dev = _device(auth_client)["device"]
    headers = {FINGERPRINT_HEADER: _fp(dev)}

    # zu früh: 365 Tage gültig, Fenster 30 Tage
    st = auth_client.get("/api/renew", headers=headers).json()
    assert st["recognized"] and st["device"] == "iPhone" and st["person"] == "Anna"
    assert not st["can_renew"] and st["opens_at"] and st["days_left"] >= 364
    assert auth_client.post("/api/renew", headers=headers).status_code == 403

    _expire_in(auth_client, dev["id"], 10)
    st = auth_client.get("/api/renew", headers=headers).json()
    assert st["can_renew"] and st["days_left"] in (9, 10)

    loaded = len(caddy.loaded)
    r = auth_client.post("/api/renew", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    key, cert, _ = pkcs12.load_key_and_certificates(
        base64.b64decode(body["p12_base64"]), body["password"].encode()
    )
    assert key is not None and cert is not None
    assert len(caddy.loaded) > loaded  # neue Freigabelisten übertragen

    # altes Zertifikat gilt nicht mehr
    old = auth_client.get("/api/renew", headers=headers).json()
    assert not old["recognized"]
    devices = auth_client.get("/api/devices").json()
    new = next(d for d in devices if d["id"] == dev["id"])
    assert _fp(new) != _fp(dev)

    audit = auth_client.get("/api/audit").json()
    e = next(e for e in audit if e["action"] == "device_renewed")
    assert e["actor"] == "Anna" and e["details"]["via"] == "selbst"


def test_disabled_and_window_setting(auth_client: TestClient) -> None:
    _setup(auth_client)
    dev = _device(auth_client)["device"]
    headers = {FINGERPRINT_HEADER: _fp(dev)}
    _expire_in(auth_client, dev["id"], 50)
    assert not auth_client.get("/api/renew", headers=headers).json()["can_renew"]

    r = auth_client.put("/api/settings/general", json={"device_self_renew_days": 60})
    assert r.status_code == 200 and r.json()["device_self_renew_days"] == 60
    assert auth_client.get("/api/renew", headers=headers).json()["can_renew"]

    r = auth_client.put("/api/settings/general", json={"device_self_renew": False})
    assert r.json()["device_self_renew"] is False
    st = auth_client.get("/api/renew", headers=headers).json()
    assert not st["enabled"] and not st["can_renew"] and "ausgeschaltet" in st["reason"]
    assert auth_client.post("/api/renew", headers=headers).status_code == 403


def test_revoked_device_cannot_renew(auth_client: TestClient) -> None:
    _setup(auth_client)
    dev = _device(auth_client)["device"]
    _expire_in(auth_client, dev["id"], 5)
    assert auth_client.post(f"/api/devices/{dev['id']}/revoke", json={}).status_code == 200
    st = auth_client.get("/api/renew", headers={FINGERPRINT_HEADER: _fp(dev)}).json()
    assert st["recognized"] and not st["can_renew"] and "gesperrt" in st["reason"]


def test_old_intermediate_renews_anytime(auth_client: TestClient) -> None:
    root = _setup(auth_client)
    dev = _device(auth_client)["device"]
    headers = {FINGERPRINT_HEADER: _fp(dev)}
    assert not auth_client.get("/api/renew", headers=headers).json()["can_renew"]
    r = auth_client.post(
        "/api/ca/rotate", json={"root_key_pem": root["root_key_pem"], "passphrase": PASS}
    )
    assert r.status_code == 200, r.text
    assert auth_client.get("/api/renew", headers=headers).json()["can_renew"]
    assert auth_client.post("/api/renew", headers=headers).status_code == 200
    assert auth_client.get("/api/ca").json()["previous"] == []


def test_public_paths_and_page() -> None:
    assert "/v" in CONTROLLER_PUBLIC_PATHS and "/api/renew" in CONTROLLER_PUBLIC_PATHS
