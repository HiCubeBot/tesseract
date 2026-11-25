"""Gerätezertifikate später abrufen: .p12 + Passwort, Download-Link (QR), löschen, abschalten."""

import base64

from cryptography.hazmat.primitives.serialization import pkcs12
from fastapi.testclient import TestClient

from tests.test_mtls import _issue, _setup


def test_view_again_and_download_link(auth_client: TestClient) -> None:
    ids = _setup(auth_client)
    r = auth_client.post(f"/api/persons/{ids['anna']['id']}/devices", json={"name": "Handy"})
    issued = r.json()
    dev = issued["device"]
    assert dev["p12_stored"] is True

    again = auth_client.get(f"/api/devices/{dev['id']}/certificate").json()
    assert again["password"] == issued["password"]
    p12 = base64.b64decode(again["p12_base64"])
    key, cert, _ = pkcs12.load_key_and_certificates(p12, again["password"].encode())
    assert key is not None and cert is not None

    link = auth_client.post(f"/api/devices/{dev['id']}/download-link").json()
    assert (
        "/api/dl/" in link["url"]
        and link["qr_svg"].startswith("<svg")
        and "viewBox=" in link["qr_svg"]
        and 'width="' not in link["qr_svg"]
    )
    token_path = "/api/dl/" + link["url"].rsplit("/api/dl/", 1)[1]
    anon = TestClient(auth_client.app)
    for _ in range(3):
        d = anon.get(token_path)
        assert d.status_code == 200 and d.content == p12
        assert "attachment" in d.headers["content-disposition"]
    assert anon.get(token_path).status_code == 404  # nach drei Abrufen verbraucht
    assert anon.get("/api/dl/falsch").status_code == 404
    assert anon.get(f"/api/devices/{dev['id']}/certificate").status_code == 401

    # Verlängern → neue Kopie mit neuem Passwort
    renewed = auth_client.post(f"/api/devices/{dev['id']}/renew", json={"days": 365}).json()
    assert (
        auth_client.get(f"/api/devices/{dev['id']}/certificate").json()["password"]
        == (renewed["password"])
    )

    # Kopie löschen
    assert auth_client.delete(f"/api/devices/{dev['id']}/certificate").status_code == 204
    assert auth_client.get(f"/api/devices/{dev['id']}/certificate").status_code == 404
    actions = [e["action"] for e in auth_client.get("/api/audit?limit=50").json()]
    assert "device_cert_viewed" in actions and "device_cert_downloaded" in actions


def test_revoke_and_switch_off(auth_client: TestClient) -> None:
    ids = _setup(auth_client)
    a = _issue(auth_client, ids["anna"]["id"], "Laptop")
    b = _issue(auth_client, ids["anna"]["id"], "Tablet")
    auth_client.post(f"/api/devices/{a['id']}/revoke", json={})
    assert auth_client.get(f"/api/devices/{a['id']}/certificate").status_code == 404
    g = auth_client.get("/api/settings/general").json()
    assert g["device_keep_p12"] is True and g["device_p12_stored"] == 1
    g = auth_client.put("/api/settings/general", json={"device_keep_p12": False}).json()
    assert g["device_keep_p12"] is False and g["device_p12_stored"] == 0
    assert auth_client.get(f"/api/devices/{b['id']}/certificate").status_code == 404
    c = _issue(auth_client, ids["anna"]["id"], "Neu")
    assert c["p12_stored"] is False
