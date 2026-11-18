"""Installationsskript für Nodes."""

import hashlib
import shutil
import subprocess

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeCaddy

ROOT_PEM = "-----BEGIN CERTIFICATE-----\nMIIBTEST\n-----END CERTIFICATE-----"


def test_script_public_domain(auth_client: TestClient) -> None:
    r = auth_client.get("/install/node.sh")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/x-shellscript")
    s = r.text
    assert s.startswith("#!/bin/sh") and 'CONTROLLER="https://tesseract.example.org"' in s
    assert "__" not in s.replace("__init__", "")  # alle Platzhalter ersetzt
    assert "TESSERACT_AGENT_CONTROLLER: ${TESSERACT_CONTROLLER:?" in s  # Compose unverändert
    assert "CA_PEM=''" in s  # öffentliche Domain: keine CA nötig
    # ohne Anmeldung erreichbar
    assert TestClient(auth_client.app).get("/install/node.sh").status_code == 200


def test_join_returns_install_command(auth_client: TestClient) -> None:
    auth_client.post("/api/ca/setup", json={"passphrase": "root-passphrase-123"})
    join = auth_client.post("/api/nodes", json={"name": "pi"}).json()["join"]
    assert join["install_command"] == (
        "curl -fsSL https://tesseract.example.org/install/node.sh | sudo sh -s -- "
        f"--token {join['token']}"
    )
    script = auth_client.get("/install/node.sh").content
    assert join["install_sha256"] == hashlib.sha256(script).hexdigest()


def test_internal_domain_ships_caddy_ca(settings, caddy: FakeCaddy) -> None:
    from tesseract.app import create_app
    from tests.conftest import ADMIN_PASSWORD  # noqa: F401

    settings.controller_domain = "tesseract.lan"
    settings.admin_password = "install-test-12345"
    app = create_app(settings)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pki/ca/local":
            return httpx.Response(200, json={"root_certificate": ROOT_PEM})
        return caddy.handler(request)

    app.state.caddy_transport = httpx.MockTransport(handler)
    with TestClient(app) as c:
        s = c.get("/install/node.sh").text
        assert f"CA_PEM='{ROOT_PEM}'" in s
        c.post("/api/auth/login", json={"username": "admin", "password": "install-test-12345"})
        c.post("/api/ca/setup", json={"passphrase": "root-passphrase-123"})
        join = c.post("/api/nodes", json={"name": "pi"}).json()["join"]
        assert join["install_command"].startswith(
            "curl -fsSLk https://tesseract.lan/install/node.sh -o tesseract-node.sh && "
        )
        assert join["install_sha256"] in join["install_command"]


@pytest.mark.skipif(shutil.which("sh") is None, reason="keine POSIX-Shell")
def test_script_syntax(auth_client: TestClient, tmp_path) -> None:
    p = tmp_path / "node.sh"
    p.write_bytes(auth_client.get("/install/node.sh").content)
    r = subprocess.run(["sh", "-n", str(p)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_compose_template_matches_repo() -> None:
    """Die Vorlage im Skript und docker/node/compose.yaml dürfen nicht auseinanderlaufen."""
    from importlib import resources
    from pathlib import Path

    bundled = (
        resources.files("tesseract.install")
        .joinpath("node-compose.yaml")
        .read_text(encoding="utf-8")
    )
    repo = Path(__file__).parents[2] / "docker" / "node" / "compose.yaml"
    assert bundled == repo.read_text(encoding="utf-8")
