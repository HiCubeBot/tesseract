"""Phase 6: CA-Wechsel, Geräte verlängern, Ablauf-Erinnerungen."""

import base64
from datetime import timedelta

from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi.testclient import TestClient

from tesseract import reminders
from tesseract.db.models import AuditEntry, Device, utcnow
from tests.conftest import FakeCaddy

PASS = "root-passphrase-123"


def _setup(c: TestClient) -> dict:
    r = c.post("/api/ca/setup", json={"passphrase": PASS})
    assert r.status_code == 200
    return r.json()


def _device(c: TestClient, name: str = "iPhone") -> dict:
    p = c.post("/api/persons", json={"name": "Anna"}).json()
    r = c.post(f"/api/persons/{p['id']}/devices", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def _trusted(caddy: FakeCaddy) -> list[str]:
    for p in caddy.last["apps"]["http"]["servers"]["https"].get("tls_connection_policies", []):
        ca = p.get("client_authentication", {}).get("ca")
        if ca:
            return ca["trusted_ca_certs"]
    return []


def test_rotate_keeps_old_trusted_until_renewed(auth_client: TestClient, caddy: FakeCaddy) -> None:
    root = _setup(auth_client)
    dev = _device(auth_client)["device"]
    before = auth_client.get("/api/ca").json()
    assert len(_trusted(caddy)) == 1

    bad = auth_client.post(
        "/api/ca/rotate", json={"root_key_pem": root["root_key_pem"], "passphrase": "falsch"}
    )
    assert bad.status_code == 409 and "falsch" in bad.json()["detail"]

    r = auth_client.post(
        "/api/ca/rotate", json={"root_key_pem": root["root_key_pem"], "passphrase": PASS}
    )
    assert r.status_code == 200, r.text
    st = r.json()
    assert st["intermediate"]["fingerprint"] != before["intermediate"]["fingerprint"]
    assert [d["name"] for d in st["previous"][0]["devices"]] == ["iPhone"]
    # Caddy vertraut beiden, bis das alte Gerät verlängert ist
    assert len(_trusted(caddy)) == 2

    renewed = auth_client.post(f"/api/devices/{dev['id']}/renew", json={"days": 365})
    assert renewed.status_code == 200, renewed.text
    body = renewed.json()
    assert body["device"]["fingerprint"] != dev["fingerprint"]
    key, cert, chain = pkcs12.load_key_and_certificates(
        base64.b64decode(body["p12_base64"]), body["password"].encode()
    )
    assert cert is not None and key is not None
    st = auth_client.get("/api/ca").json()
    assert st["previous"] == []
    assert len(_trusted(caddy)) == 1
    actions = [e["action"] for e in auth_client.get("/api/audit").json()]
    assert {"ca_rotated", "device_renewed"} <= set(actions)


def test_rotate_rejects_foreign_root(auth_client: TestClient) -> None:
    _setup(auth_client)
    from tesseract import pki

    other = pki.generate_root()
    r = auth_client.post(
        "/api/ca/rotate",
        json={"root_key_pem": pki.key_pem(other.key, PASS), "passphrase": PASS},
    )
    assert r.status_code == 409 and "gehört nicht" in r.json()["detail"]


def test_renew_revoked_device_refused(auth_client: TestClient) -> None:
    _setup(auth_client)
    dev = _device(auth_client)["device"]
    auth_client.post(f"/api/devices/{dev['id']}/revoke", json={"reason": "verloren"})
    r = auth_client.post(f"/api/devices/{dev['id']}/renew", json={"days": 30})
    assert r.status_code == 409


def test_reminders_once_per_threshold(auth_client: TestClient) -> None:
    _setup(auth_client)
    dev = _device(auth_client)["device"]
    with auth_client.app.state.db.sessionmaker() as db:
        d = db.get(Device, dev["id"])
        d.not_after = utcnow() + timedelta(days=20)
        db.commit()
        assert reminders.check(db) == [f"device:{d.id}:{d.serial}:30"]
        db.commit()
        assert reminders.check(db) == []  # nicht doppelt
        d.not_after = utcnow() + timedelta(days=5)
        db.commit()
        assert reminders.check(db) == [f"device:{d.id}:{d.serial}:7"]
        db.commit()
        entries = list(db.query(AuditEntry).filter(AuditEntry.action == "device_expiring"))
    assert len(entries) == 2 and entries[0].target == "Anna · iPhone"
    from tesseract.notify import ACTION_EVENT, describe

    assert ACTION_EVENT["device_expiring"] == "device_expiring"
    assert "verlängern" in describe(entries[-1])
