"""Oberfläche nur mit Admin-Zertifikat."""

import hashlib

from fastapi.testclient import TestClient

from tesseract.caddy.config import (
    CONTROLLER_PUBLIC_PATHS,
    FINGERPRINT,
    FINGERPRINT_HEADER,
    path_patterns,
)
from tesseract.cli import admin_mtls_off
from tests.conftest import ADMIN_PASSWORD, FakeCaddy


def _admin_device(c: TestClient) -> str:
    assert c.post("/api/ca/setup", json={"passphrase": "root-passphrase-123"}).status_code == 200
    admin_group = next(g for g in c.get("/api/groups").json() if g["name"] == "Admin")
    me = c.post("/api/persons", json={"name": "Ich", "group_ids": [admin_group["id"]]}).json()
    dev = c.post(f"/api/persons/{me['id']}/devices", json={"name": "ThinkPad"}).json()["device"]
    return dev["fingerprint"].replace(":", "").lower()


def _controller_route(caddy: FakeCaddy) -> dict:
    routes = caddy.last["apps"]["http"]["servers"]["https"]["routes"]
    return next(r for r in routes if r.get("@id") == "controller")


def test_controller_passes_fingerprint_header(auth_client: TestClient, caddy: FakeCaddy) -> None:
    _admin_device(auth_client)
    route = _controller_route(caddy)
    sub = route["handle"][0]["routes"]
    proxy = sub[-1]["handle"][0]
    assert proxy["headers"]["request"]["set"][FINGERPRINT_HEADER] == [FINGERPRINT]
    # Noch nicht geschützt: keine Sperr-Route, aber Zertifikat wird erfragt (Geräteerkennung)
    assert len(sub) == 1
    policies = caddy.last["apps"]["http"]["servers"]["https"]["tls_connection_policies"]
    ctl = next(p for p in policies if p.get("match", {}).get("sni") == ["tesseract.example.org"])
    assert ctl["client_authentication"]["mode"] == "verify_if_given"


def test_device_detection(auth_client: TestClient) -> None:
    fp = _admin_device(auth_client)
    r = auth_client.get("/api/auth/device", headers={FINGERPRINT_HEADER: fp})
    assert r.json() == {"certificate": True, "admin_device": "ThinkPad", "person": "Ich"}
    r = auth_client.get("/api/auth/device", headers={FINGERPRINT_HEADER: "ab" * 32})
    assert r.json()["admin_device"] is None and r.json()["certificate"] is True
    # Unaufgelöster Platzhalter o. Ä. zählt nicht als Zertifikat
    for value in ("<empty>", hashlib.sha256(b"").hexdigest()):
        r = auth_client.get("/api/auth/device", headers={FINGERPRINT_HEADER: value})
        assert r.json()["certificate"] is False


def test_enable_requires_current_admin_device(auth_client: TestClient, caddy: FakeCaddy) -> None:
    # ohne Admin-Gerät
    r = auth_client.put("/api/settings/admin-access", json={"enabled": True})
    assert r.status_code == 409 and "Admin" in r.json()["detail"]

    fp = _admin_device(auth_client)
    # Admin-Gerät existiert, aber diese Anfrage kommt ohne Zertifikat
    r = auth_client.put("/api/settings/admin-access", json={"enabled": True})
    assert r.status_code == 409 and "Admin-Zertifikat" in r.json()["detail"]

    headers = {FINGERPRINT_HEADER: fp}
    state = auth_client.get("/api/settings/admin-access", headers=headers).json()
    assert state["can_enable"] and state["current_device"] == "Ich · ThinkPad"
    r = auth_client.put("/api/settings/admin-access", json={"enabled": True}, headers=headers)
    assert r.status_code == 200 and r.json()["enabled"] is True

    # Caddy: Oberfläche gesperrt, Einladungsseite & Dateien bleiben öffentlich
    gate = _controller_route(caddy)["handle"][0]["routes"][0]
    negations = gate["match"][0]["not"]
    assert negations[0]["vars"][FINGERPRINT] == [fp]
    assert negations[1]["path"] == path_patterns(CONTROLLER_PUBLIC_PATHS)

    # Backend erzwingt es ebenfalls
    assert auth_client.get("/api/hosts").status_code == 403
    assert auth_client.get("/api/hosts", headers=headers).status_code == 200
    auth_client.cookies.clear()
    r = auth_client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert r.status_code == 403
    r = auth_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": ADMIN_PASSWORD},
        headers=headers,
    )
    assert r.status_code == 200
    # Öffentliche Endpunkte bleiben erreichbar
    assert auth_client.get("/api/health").status_code == 200
    assert auth_client.get("/api/enroll/unbekannt").status_code == 404


def test_cli_off(auth_client: TestClient, settings, monkeypatch) -> None:
    fp = _admin_device(auth_client)
    headers = {FINGERPRINT_HEADER: fp}
    auth_client.put("/api/settings/admin-access", json={"enabled": True}, headers=headers)
    assert auth_client.get("/api/hosts").status_code == 403

    monkeypatch.setattr("tesseract.cli.get_settings", lambda: settings)
    admin_mtls_off()
    assert auth_client.get("/api/hosts").status_code == 200


def test_revoked_admin_device_loses_access(auth_client: TestClient) -> None:
    fp = _admin_device(auth_client)
    headers = {FINGERPRINT_HEADER: fp}
    auth_client.put("/api/settings/admin-access", json={"enabled": True}, headers=headers)
    dev = next(d for d in auth_client.get("/api/devices", headers=headers).json())
    auth_client.post(f"/api/devices/{dev['id']}/revoke", json={}, headers=headers)
    assert auth_client.get("/api/hosts", headers=headers).status_code == 403
