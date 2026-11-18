from fastapi.testclient import TestClient

from tesseract.app import create_app
from tesseract.config import Settings


def test_health() -> None:
    client = TestClient(create_app(Settings(static_dir=None)))
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
