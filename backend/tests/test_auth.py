from fastapi.testclient import TestClient

from tests.conftest import ADMIN_PASSWORD


def test_requires_login(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/audit").status_code == 401


def test_login_logout(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert client.get("/api/auth/me").json() == {"username": "admin", "password_from_env": False}

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_wrong_password_is_audited_and_throttled(client: TestClient) -> None:
    for _ in range(5):
        r = client.post("/api/auth/login", json={"username": "admin", "password": "falsch"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert r.status_code == 429


def test_remember_sets_persistent_cookie(client: TestClient) -> None:
    r = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": ADMIN_PASSWORD, "remember": True},
    )
    assert "Max-Age=2592000" in r.headers["set-cookie"]


def test_change_password_ends_sessions(auth_client: TestClient) -> None:
    r = auth_client.post(
        "/api/auth/password",
        json={"current_password": ADMIN_PASSWORD, "new_password": "ein-neues-passwort"},
    )
    assert r.status_code == 204
    assert auth_client.get("/api/auth/me").status_code == 401
    r = auth_client.post(
        "/api/auth/login", json={"username": "admin", "password": "ein-neues-passwort"}
    )
    assert r.status_code == 200


def test_audit_lists_logins(auth_client: TestClient) -> None:
    entries = auth_client.get("/api/audit").json()
    assert entries[0]["action"] == "login"
    assert entries[0]["actor"] == "admin"
