"""Zahlen für die Seitenleiste und Verbindungsangaben der Nodes."""

from fastapi.testclient import TestClient

from tesseract.api.nodes import _network
from tests.test_hosts import HOST


def test_counts(auth_client: TestClient) -> None:
    c = auth_client.get("/api/counts").json()
    assert c == {"hosts": 0, "persons": 0, "devices": 0, "nodes": 1}
    auth_client.post("/api/hosts", json=HOST)
    assert auth_client.get("/api/counts").json()["hosts"] == 1


def test_counts_need_login(client: TestClient) -> None:
    assert client.get("/api/counts").status_code == 401


def test_nodes_public_hosts(auth_client: TestClient) -> None:
    auth_client.post("/api/hosts", json=HOST)
    auth_client.post(
        "/api/hosts",
        json={**HOST, "domain": "intern.example.org", "internal": False, "access": "mtls"},
    )
    local = auth_client.get("/api/nodes").json()[0]
    assert local["hosts"] >= 1 and local["hosts_public"] == 1
    assert local["controller_url"] is None and local["network"] is None


def test_network_kind() -> None:
    assert _network("10.0.4.2", []) == "privat"
    assert _network("10.0.4.2", ["10.0.0.0/16"]) == "intern"
    assert _network("100.72.1.5", []) == "privat"
    assert _network("217.80.188.26", []) == "internet"
    assert _network("fd00::1", []) == "privat"
    assert _network(None, []) is None and _network("kaputt", []) is None
