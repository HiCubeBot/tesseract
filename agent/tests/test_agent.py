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
        self.access: list[list[str]] = []
        self.down = False
        self.csr: str | None = None
        self.want_metrics = False
        self.renewed: str | None = None
        self.new_cert = ""

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
        if path == "/api/agent/renew":
            self.renewed = json.loads(request.content)["csr"]
            return httpx.Response(
                200, json={"cert_pem": self.new_cert, "chain_pem": "CHAIN2", "not_after": "x"}
            )
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
            return httpx.Response(200, json={"ok": True, "caddy_metrics": self.want_metrics})
        if path == "/api/agent/logs":
            body = json.loads(request.content)
            self.waf.append(body["waf"])
            self.access.append(body["access"])
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
        if request.url.path == "/metrics":
            return httpx.Response(200, text="# TYPE caddy_x counter\ncaddy_x 3\ngo_goroutines 9\n")
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
        access_log=tmp_path / "access.log",
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


def test_logs_buffered_while_offline(env):
    ctrl, _, settings, make = env
    agent = joined(env)
    waf, acc = settings.waf_log, settings.access_log
    waf.write_text("")
    acc.write_text('{"alt": true}\n')
    agent.logs_round()  # merkt sich die Dateienden
    hit = json.dumps({"msg": "WAF rule violation detected", "client_ip": "203.0.113.9"})
    req = json.dumps({"msg": "handled request", "status": 403})
    with waf.open("a") as f:
        f.write(hit + "\n")
    with acc.open("a") as f:
        f.write(req + "\n")
    ctrl.down = True
    with pytest.raises(httpx.ConnectError):
        agent.logs_round()
    assert agent.logs.pending() == [("a", req), ("w", hit)]
    # Neustart des Agents: Puffer und Lesestand bleiben erhalten
    ctrl.down = False
    again = make()
    assert again.logs_round() == 2
    assert ctrl.waf == [[hit]] and ctrl.access == [[req]]
    assert again.logs.pending() == []


def test_old_buffer_format_is_shipped_as_waf(env):
    ctrl, _, settings, make = env
    agent = joined(env)
    settings.buffer_file.write_text("alte-waf-zeile\n")
    assert agent.logs.ship(agent.send_logs) == 1
    assert ctrl.waf == [["alte-waf-zeile"]] and ctrl.access == [[]]


def test_cli_status_and_missing_token(env, capsys, monkeypatch):
    _, _, settings, _ = env
    monkeypatch.delenv("TESSERACT_AGENT_JOIN_TOKEN", raising=False)
    assert main(["--data-dir", str(settings.data_dir), "status"]) == 0
    assert "Nicht beigetreten" in capsys.readouterr().out
    rc = main(["--data-dir", str(settings.data_dir), "run", "--controller", "https://x"])
    assert rc == 1
    assert "Beitritts-Token fehlt" in capsys.readouterr().err


def test_caddy_metrics_only_when_wanted(env):
    ctrl, _, _, _ = env
    agent = joined(env)
    agent.send_status()
    assert "caddy_metrics" not in ctrl.status[-1]
    ctrl.want_metrics = True
    agent.send_status()  # Antwort schaltet es ein
    agent.send_status()
    assert ctrl.status[-1]["caddy_metrics"] == "# TYPE caddy_x counter" + chr(10) + "caddy_x 3"


def _self_signed(days: int) -> str:
    from datetime import UTC, datetime, timedelta

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pi")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=days))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def test_cert_renewal_before_expiry(env):
    ctrl, _, settings, _ = env
    agent = joined(env)
    settings.cert_file.write_text(_self_signed(300))
    assert agent.renew_if_due() is False and ctrl.renewed is None
    settings.cert_file.write_text(_self_signed(30))
    old_key = settings.key_file.read_bytes()
    ctrl.new_cert = _self_signed(700)
    agent.send_status()  # prüft dabei die Laufzeit
    assert ctrl.renewed and "CERTIFICATE REQUEST" in ctrl.renewed
    assert settings.cert_file.read_text() == ctrl.new_cert
    assert settings.key_file.read_bytes() != old_key
    assert settings.chain_file.read_text() == "CHAIN2"
