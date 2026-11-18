from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tesseract.app import create_app
from tesseract.auth import hash_password
from tesseract.config import Settings
from tesseract.db.models import Admin

ADMIN_PASSWORD = "test-passwort-123"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        static_dir=None,
        cookie_secure=False,
        caddy_admin_url="http://caddy.invalid:2019",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as c:
        with app.state.db.sessionmaker() as db:
            admin = db.scalar(select(Admin).where(Admin.username == "admin"))
            admin.password_hash = hash_password(ADMIN_PASSWORD)
            db.commit()
        yield c


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    r = client.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return client
