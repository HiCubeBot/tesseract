import base64
import json
from pathlib import Path

import httpx
import pytest
from cryptography import x509

from tesseract_agent.agent import Agent, AgentError, config_hash
from tesseract_agent.cli import main
from tesseract_agent.config import Settings, State


class FakeController:
    def __init__(self) -> None:
        self.approved = False
        self.config = {"apps": {"http": {}}}
        self.force = 0
        self.status: list[dict] = []
        self.waf: list[list[str]] = []
        self.down = False
        self.csr: str | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("weg")
        path = request.url.path
        if path == "/api/agent/join":
            body = json.loads(request.content)
            if body["token"] != "gut":
                return httpx.Response(403, json={"detail": "Token ungültig"})
            self.csr = body["csr"]
            return httpx.Response(200, json={"node_id": 7, "name": "pi", "secret": "s3"})
        if path == "/api/agent/join/7":
            assert request.headers["X-Join-Secret"] == "s3"
            if not self.approved:
                return httpx.Response(202, json={"state": "pending"})
            return httpx.Response(
                200,
                json={"cert_pem": "CERT", "chain_pem": "CHAIN", "agent_token": "tok"},
            )
        assert request.headers["Authorization"] == "Bearer tok"
        if path == "/api/agent/config":
            known = request.url.params["known"]
            force = int(request.url.params["force"])
            digest = config_hash(self.config)
            if known == digest and force == self.force:
                return httpx.Response(204)
            return httpx.Response(
                200, json={"hash": digest, "force": self.force, "config": self.config}
            )
        if path == "/api/agent/status":
            self.status.append(json.loads(request.content))
            return httpx.Response(200, json={"ok": True})
        if path == "/api/agent/waf":
            self.waf.append(json.loads(request.content)["lines"])
            return httpx.Response(200, json={"accepted": 1})
        return httpx.Response(404)


class FakeCaddy:
    def __init__(self) -> None:
        self.running: dict = {}
        self.loads = 0
        self.reject = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/load":
            if self.reject:
                return httpx.Response(400, json={"error": "kaputt"})
            self.loads += 1
            self.running = json.loads(request.content)
            return httpx.Response(200)
        if request.url.path == "/config/":
            return httpx.Response(200, json=self.running)
        if request.url.path == "/adapt":
            ok = b"coraza_waf" in request.content
            return httpx.Response(200 if ok else 400, json={})
        return httpx.Response(404)


@pytest.fixture
def env(tmp_path: Path):
    ctrl, caddy = FakeController(), FakeCaddy()
    settings = Settings(
        data_dir=tmp_path,
        controller="https://ctrl.example.org",
        waf_log=tmp_path / "waf.log",
        caddy_bin="gibt-es-nicht",
    )

    def make() -> Agent:
        return Agent(
            settings,
            controller_transport=httpx.MockTransport(ctrl.handler),
            caddy_transport=httpx.MockTransport(caddy.handler),
        )

    return ctrl, caddy, settings, make


def joined(env) -> Agent:
    ctrl, _, _, make = env
    agent = make()
    agent.join("https://ctrl.example.org", "gut", "pi-host")
    ctrl.approved = True
    agent.wait_for_approval(interval=0)
    return agent


def test_join_creates_key_and_waits_for_approval(env):
    ctrl, _, settings, make = env
    agent = make()
    fp = agent.join("https://ctrl.example.org", "gut", "pi-host")
    csr = x509.load_pem_x509_csr(ctrl.csr.encode())
    assert csr.is_signature_valid
    assert len(fp) == 64
    assert settings.key_file.exists()
    with pytest.raises(AgentError, match="Zeitüberschreitung"):
        agent.wait_for_approval(interval=0, timeout=0)
    ctrl.approved = True
    agent.wait_for_approval(interval=0)
    state = State.load(settings.state_file)
    assert state.joined and state.agent_token == "tok" and not state.join_secret
    assert settings.cert_file.read_text() == "CERT"


def test_wrong_token(env):
    *_, make = env
    with pytest.raises(AgentError, match="Token ungültig"):
        make().join("https://ctrl.example.org", "falsch")


def test_config_loaded_once_and_forced(env):
    ctrl, caddy, _, _ = env
    agent = joined(env)
    assert agent.poll_config(wait=0) is True
    assert caddy.running == ctrl.config
    assert agent.poll_config(wait=0) is False
    assert caddy.loads == 1
    ctrl.force = 1  # „Mit Controller überschreiben“
    assert agent.poll_config(wait=0) is True
    assert caddy.loads == 2


def test_rejected_config_not_retried_until_change(env):
    ctrl, caddy, _, _ = env
    agent = joined(env)
    caddy.reject = True
    assert agent.poll_config(wait=0) is False
    assert "kaputt" in agent.load_error
    assert agent.poll_config(wait=0) is False  # gleiche Config: kein neuer Versuch
    caddy.reject = False
    ctrl.config = {"apps": {"http": {"servers": {}}}}
    assert agent.poll_config(wait=0) is True
    assert agent.load_error is None


def test_status_reports_drift_with_running_config(env):
    ctrl, caddy, _, _ = env
    agent = joined(env)
    agent.poll_config(wait=0)
    agent.send_status()
    first = ctrl.status[-1]
    assert first["running_hash"] == first["loaded_hash"]
    assert "running_config_b64" not in first
    assert first["modules"] == ["http.handlers.waf"]
    caddy.running = {"apps": {"http": {"lokal": True}}}  # jemand ändert Caddy direkt
    agent.send_status()
    second = ctrl.status[-1]
    assert second["running_hash"] != second["loaded_hash"]
    assert json.loads(base64.b64decode(second["running_config_b64"])) == caddy.running


def test_waf_hits_buffered_while_offline(env):
    ctrl, _, settings, make = env
    agent = joined(env)
    log = settings.waf_log
    log.write_text("")
    agent.waf_round()  # merkt sich das Dateiende
    hit = json.dumps({"msg": "WAF rule violation detected", "client_ip": "203.0.113.9"})
    with log.open("a") as f:
        f.write(hit + "\n" + json.dumps({"msg": "anderes"}) + "\n")
    ctrl.down = True
    with pytest.raises(httpx.ConnectError):
        agent.waf_round()
    assert agent.waf.pending() == [hit]
    # Neustart des Agents: Puffer und Lesestand bleiben erhalten
    ctrl.down = False
    again = make()
    assert again.waf_round() == 1
    assert ctrl.waf == [[hit]]
    assert again.waf.pending() == []


def test_cli_status_and_missing_token(env, capsys, monkeypatch):
    _, _, settings, _ = env
    monkeypatch.delenv("TESSERACT_AGENT_JOIN_TOKEN", raising=False)
    assert main(["--data-dir", str(settings.data_dir), "status"]) == 0
    assert "Nicht beigetreten" in capsys.readouterr().out
    rc = main(["--data-dir", str(settings.data_dir), "run", "--controller", "https://x"])
    assert rc == 1
    assert "Beitritts-Token fehlt" in capsys.readouterr().err
