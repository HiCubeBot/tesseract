import json
from collections.abc import Iterator
from pathlib import Path

import httpx
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
        controller_domain="tesseract.example.org",
        sync_on_start=False,
        background_tasks=False,
    )


class FakeCaddy:
    """Nimmt POST /load entgegen und merkt sich die Configs."""

    def __init__(self) -> None:
        self.loaded: list[dict] = []
        self.fail_with: str | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/load":
            if self.fail_with:
                return httpx.Response(400, json={"error": self.fail_with})
            self.loaded.append(json.loads(request.content))
            return httpx.Response(200)
        return httpx.Response(404)

    @property
    def last(self) -> dict:
        return self.loaded[-1]


@pytest.fixture
def caddy() -> FakeCaddy:
    return FakeCaddy()


@pytest.fixture
def client(settings: Settings, caddy: FakeCaddy) -> Iterator[TestClient]:
    app = create_app(settings)
    app.state.caddy_transport = httpx.MockTransport(caddy.handler)
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
