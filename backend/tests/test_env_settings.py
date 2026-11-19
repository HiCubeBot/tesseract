"""Admin-Passwort und Einstellungen aus der Umgebung (.env)."""

import pytest
from fastapi.testclient import TestClient

from tesseract.app import create_app
from tesseract.config import Settings

PW = "env-passwort-1234"


def _client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def test_admin_password_from_env(settings: Settings, tmp_path) -> None:
    settings.admin_password = PW
    settings.admin_username = "chef"
    with _client(settings) as c:
        r = c.post("/api/auth/login", json={"username": "chef", "password": PW})
        assert r.status_code == 200
        assert c.get("/api/auth/me").json() == {
            "username": "chef",
            "password_from_env": True,
            "source": "local",
        }
        r = c.post(
            "/api/auth/password",
            json={"current_password": PW, "new_password": "anderes-passwort-99"},
        )
        assert r.status_code == 409 and "TESSERACT_ADMIN_PASSWORD" in r.json()["detail"]

    # Neuer Start mit anderem Passwort: es wird durchgesetzt
    settings.admin_password = ""
    secret = tmp_path / "pw.txt"
    secret.write_text("neues-passwort-5678\n")
    settings.admin_password_file = secret
    with _client(settings) as c:
        assert (
            c.post("/api/auth/login", json={"username": "chef", "password": PW}).status_code == 401
        )
        r = c.post("/api/auth/login", json={"username": "chef", "password": "neues-passwort-5678"})
        assert r.status_code == 200
        actions = [e["action"] for e in c.get("/api/audit").json()]
        assert "password_reset" in actions


def test_short_password_refused(settings: Settings) -> None:
    settings.admin_password = "kurz"
    with pytest.raises(ValueError, match="zu kurz"), _client(settings):
        pass


def test_settings_overrides(settings: Settings) -> None:
    settings.admin_password = PW
    settings.acme_email = "le@example.org"
    settings.logs_days = 30
    settings.internal_networks = "192.168.178.0/24, 10.8.0.0/24"
    with _client(settings) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": PW})
        g = c.get("/api/settings/general").json()
        assert g["acme_email"] == "le@example.org"
        assert g["internal_networks"] == ["192.168.178.0/24", "10.8.0.0/24"]
        assert g["env_managed"] == ["acme_email", "internal_networks", "logs_days"]
        assert c.get("/api/settings/observability").json()["logs_days"] == 30
