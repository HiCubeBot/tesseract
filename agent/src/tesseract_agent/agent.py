"""Beitritt und Arbeitsschleifen des Agents.

- Config:  Long-Polling `GET /api/agent/config` – neue Config wird per `POST /load` in Caddy
           geladen. Caddy rollt bei Fehlern selbst zurück; ohne Controller läuft der letzte
           Stand weiter.
- Status:  alle 30 s (und nach jedem Laden) – laufende Config (Abweichung), Module, Version.
- WAF:     neue Treffer aus Caddys WAF-Log landen erst in einem Puffer auf der Platte und
           werden nachgeliefert, sobald der Controller erreichbar ist.
"""

import base64
import hashlib
import json
import logging
import shutil
import socket
import ssl
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from tesseract_agent import __version__
from tesseract_agent.config import Settings, State, write_private

log = logging.getLogger("tesseract_agent")

# Gleiche Prüfungen wie der Controller (tesseract.nodes.MODULE_PROBES)
MODULE_PROBES: dict[str, str] = {
    "http.handlers.waf": "{\n\torder coraza_waf first\n}\n:1 {\n\tcoraza_waf\n}\n",
    "dns.providers.cloudflare": ":1 {\n\ttls {\n\t\tdns cloudflare probe\n\t}\n}\n",
}
VIOLATION = "WAF rule violation detected"
LONG_POLL = 25
HEARTBEAT = 30.0
MODULES_EVERY = 600.0
WAF_EVERY = 5.0
WAF_BATCH = 1000
WAF_BUFFER_MAX = 50_000


class AgentError(Exception):
    pass


def config_hash(config: Any) -> str:
    """Wie im Controller: SHA-256 über kanonisches JSON."""
    raw = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def public_key_fingerprint(key: ec.EllipticCurvePublicKey) -> str:
    der = key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return hashlib.sha256(der).hexdigest()


def format_fp(fp: str) -> str:
    return ":".join(fp[i : i + 2] for i in range(0, len(fp), 2)).upper()


# ---------- Caddy ----------


class Caddy:
    def __init__(self, admin_url: str, transport: httpx.BaseTransport | None = None) -> None:
        self.http = httpx.Client(base_url=admin_url, timeout=30.0, transport=transport)

    def load(self, config: dict[str, Any]) -> None:
        r = self.http.post("/load", json=config)
        if r.status_code >= 400:
            try:
                msg = r.json().get("error", r.text)
            except ValueError:
                msg = r.text
            raise AgentError(f"Caddy {r.status_code}: {str(msg)[:1000]}")

    def running(self) -> dict[str, Any]:
        r = self.http.get("/config/")
        r.raise_for_status()
        return r.json() or {}

    def modules(self) -> list[str]:
        found = []
        for name, caddyfile in MODULE_PROBES.items():
            r = self.http.post(
                "/adapt", content=caddyfile, headers={"Content-Type": "text/caddyfile"}
            )
            if r.status_code < 400:
                found.append(name)
        return found


def caddy_version(binary: str) -> str | None:
    path = shutil.which(binary) if binary else None
    if not path:
        return None
    try:
        out = subprocess.run([path, "version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    first = (out.stdout or "").strip().split(" ")[0]
    return first or None


# ---------- WAF-Log ----------


class WafShipper:
    """Liest neue Zeilen aus dem WAF-Log in einen Puffer und liefert sie aus."""

    def __init__(self, log_path: Path | None, buffer: Path) -> None:
        self.log_path = log_path
        self.buffer = buffer

    def collect(self, state: State) -> int:
        """Neue Treffer in den Puffer schreiben. Gibt die Anzahl zurück."""
        if self.log_path is None:
            return 0
        try:
            size = self.log_path.stat().st_size
        except FileNotFoundError:
            return 0
        if state.waf_offset is None:
            # Erster Start: nur Neues melden
            state.waf_offset = size
            return 0
        if size < state.waf_offset:
            state.waf_offset = 0  # rotiert
        if size == state.waf_offset:
            return 0
        with self.log_path.open("rb") as f:
            f.seek(state.waf_offset)
            data = f.read(8 * 1024 * 1024)
        cut = data.rfind(b"\n") + 1
        state.waf_offset += cut
        hits = [
            line for line in data[:cut].decode("utf-8", "replace").splitlines() if VIOLATION in line
        ]
        if hits:
            self.buffer.parent.mkdir(parents=True, exist_ok=True)
            with self.buffer.open("a", encoding="utf-8") as f:
                f.writelines(h + "\n" for h in hits)
            self._trim()
        return len(hits)

    def _trim(self) -> None:
        lines = self.pending()
        if len(lines) > WAF_BUFFER_MAX:
            self._write(lines[-WAF_BUFFER_MAX:])

    def pending(self) -> list[str]:
        if not self.buffer.exists():
            return []
        return [x for x in self.buffer.read_text(encoding="utf-8").splitlines() if x]

    def _write(self, lines: list[str]) -> None:
        tmp = self.buffer.with_suffix(".tmp")
        tmp.write_text("".join(x + "\n" for x in lines), encoding="utf-8")
        tmp.replace(self.buffer)

    def ship(self, send) -> int:
        """Puffer in Paketen senden; was nicht ankommt, bleibt liegen."""
        lines = self.pending()
        sent = 0
        while sent < len(lines):
            send(lines[sent : sent + WAF_BATCH])
            sent = min(sent + WAF_BATCH, len(lines))
            self._write(lines[sent:])
        return sent


# ---------- Agent ----------


class Agent:
    def __init__(
        self,
        settings: Settings,
        controller_transport: httpx.BaseTransport | None = None,
        caddy_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.state = State.load(settings.state_file)
        self._controller_transport = controller_transport
        self.caddy = Caddy(settings.caddy_admin_url, caddy_transport)
        self.waf = WafShipper(settings.waf_log, settings.buffer_file)
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.load_error: str | None = None
        self.rejected_hash = ""
        self._modules: list[str] | None = None
        self._modules_at = 0.0
        self._version = caddy_version(settings.caddy_bin or "caddy")

    # --- Verbindung ---

    def _ssl(self, with_cert: bool) -> ssl.SSLContext:
        ca = self.settings.controller_ca
        ctx = ssl.create_default_context(cafile=str(ca) if ca else None)
        if with_cert:
            ctx.load_cert_chain(self.settings.cert_file, self.settings.key_file)
        return ctx

    def _http(self, with_cert: bool, timeout: float = 30.0) -> httpx.Client:
        base = self.state.controller or self.settings.controller
        if not base:
            raise AgentError(
                "Controller-Adresse fehlt (--controller oder TESSERACT_AGENT_CONTROLLER)"
            )
        kwargs: dict[str, Any] = {"base_url": base, "timeout": timeout}
        if self._controller_transport is not None:
            kwargs["transport"] = self._controller_transport
        else:
            kwargs["verify"] = self._ssl(with_cert)
        headers = {"User-Agent": f"tesseract-agent/{__version__}"}
        if with_cert:
            headers["Authorization"] = f"Bearer {self.state.agent_token}"
        return httpx.Client(headers=headers, **kwargs)

    def save(self) -> None:
        with self.lock:
            self.state.save(self.settings.state_file)

    # --- Beitritt ---

    def join(self, controller: str, token: str, hostname: str = "") -> str:
        """Schlüssel erzeugen, Anfrage stellen. Gibt den Schlüssel-Fingerabdruck zurück."""
        hostname = hostname or socket.gethostname()
        key = ec.generate_private_key(ec.SECP256R1())
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname[:64])]))
            .sign(key, hashes.SHA256())
        )
        self.state = State(controller=controller.rstrip("/"))
        with self._http(with_cert=False) as c:
            r = c.post(
                "/api/agent/join",
                json={
                    "token": token,
                    "csr": csr.public_bytes(serialization.Encoding.PEM).decode(),
                    "hostname": hostname,
                    "agent_version": __version__,
                    "admin_listen": self.settings.caddy_admin_listen,
                },
            )
        if r.status_code != 200:
            raise AgentError(f"Beitritt abgelehnt ({r.status_code}): {_detail(r)}")
        data = r.json()
        write_private(
            self.settings.key_file,
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        )
        self.state.node_id = data["node_id"]
        self.state.name = data["name"]
        self.state.join_secret = data["secret"]
        self.state.key_fingerprint = public_key_fingerprint(key.public_key())
        self.save()
        return self.state.key_fingerprint

    def wait_for_approval(self, interval: float = 5.0, timeout: float | None = None) -> None:
        """Wartet, bis der Admin den Node bestätigt, und holt Zertifikat + Token ab."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self.stop.is_set():
            with self._http(with_cert=False) as c:
                r = c.get(
                    f"/api/agent/join/{self.state.node_id}",
                    headers={"X-Join-Secret": self.state.join_secret},
                )
            if r.status_code == 200:
                data = r.json()
                self.settings.cert_file.write_text(data["cert_pem"], encoding="utf-8")
                self.settings.chain_file.write_text(data["chain_pem"], encoding="utf-8")
                self.state.agent_token = data["agent_token"]
                self.state.join_secret = ""
                self.save()
                log.info("Beitritt bestätigt – Node „%s“", self.state.name)
                return
            if r.status_code != 202:
                raise AgentError(f"Beitritt fehlgeschlagen ({r.status_code}): {_detail(r)}")
            if deadline is not None and time.monotonic() > deadline:
                raise AgentError("Zeitüberschreitung beim Warten auf die Bestätigung")
            self.stop.wait(interval)

    # --- Config ---

    def poll_config(self, wait: int = LONG_POLL) -> bool:
        """Einmal abfragen; lädt neue Config in Caddy. True, wenn geladen wurde."""
        # Hat Caddy eine Config abgelehnt, erst bei der nächsten Änderung wieder versuchen
        known = self.rejected_hash or self.state.loaded_hash
        params = {"known": known, "force": self.state.force, "wait": wait}
        with self._http(with_cert=True, timeout=wait + 15) as c:
            r = c.get("/api/agent/config", params=params)
        if r.status_code == 204:
            return False
        if r.status_code != 200:
            raise AgentError(f"Config abholen fehlgeschlagen ({r.status_code}): {_detail(r)}")
        data = r.json()
        try:
            self.caddy.load(data["config"])
        except AgentError as e:
            # Caddy hat die Config abgelehnt und läuft mit dem alten Stand weiter
            self.load_error = str(e)
            self.rejected_hash = data["hash"]
            self.state.force = data["force"]
            self.save()
            log.error("Config von Caddy abgelehnt: %s", e)
            self.wake.set()
            return False
        # httpx.HTTPError (Caddy nicht erreichbar) geht nach oben → neuer Versuch mit Pause
        self.load_error = None
        self.rejected_hash = ""
        self.state.loaded_hash = data["hash"]
        self.state.force = data["force"]
        self.save()
        log.info("Neue Config geladen (%s)", data["hash"][:12])
        self.wake.set()
        return True

    # --- Status ---

    def status_report(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "agent_version": __version__,
            "caddy_version": self._version,
            "admin_listen": self.settings.caddy_admin_listen,
            "loaded_hash": self.state.loaded_hash or None,
            "load_error": self.load_error,
        }
        try:
            running = self.caddy.running()
            digest = config_hash(running)
            report["running_hash"] = digest
            if self.state.loaded_hash and digest != self.state.loaded_hash:
                raw = json.dumps(running, separators=(",", ":")).encode()
                report["running_config_b64"] = base64.b64encode(raw).decode()
            if self._modules is None or time.monotonic() - self._modules_at > MODULES_EVERY:
                self._modules = self.caddy.modules()
                self._modules_at = time.monotonic()
            report["modules"] = self._modules
        except httpx.HTTPError as e:
            report["load_error"] = self.load_error or f"Caddy nicht erreichbar: {e}"
        return report

    def send_status(self) -> None:
        with self._http(with_cert=True) as c:
            r = c.post("/api/agent/status", json=self.status_report())
        if r.status_code != 200:
            raise AgentError(f"Status senden fehlgeschlagen ({r.status_code}): {_detail(r)}")

    def send_waf(self, lines: list[str]) -> None:
        with self._http(with_cert=True) as c:
            r = c.post("/api/agent/waf", json={"lines": lines})
        if r.status_code != 200:
            raise AgentError(f"WAF-Treffer senden fehlgeschlagen ({r.status_code})")

    def waf_round(self) -> int:
        with self.lock:
            self.waf.collect(self.state)
            self.state.save(self.settings.state_file)
        return self.waf.ship(self.send_waf)

    # --- Schleifen ---

    def _loop(self, name: str, fn, pause: float, wake: threading.Event | None = None) -> None:
        """Ruft `fn` immer wieder auf; bei Fehlern mit wachsender Pause (bis 60 s)."""
        backoff = 2.0
        while not self.stop.is_set():
            try:
                fn()
                backoff = 2.0
                if wake is not None:
                    # Status: alle `pause` Sekunden oder sofort nach dem Laden einer Config
                    wake.wait(pause)
                    wake.clear()
                elif pause:
                    self.stop.wait(pause)
            except (AgentError, httpx.HTTPError, OSError) as e:
                log.warning("%s: %s – neuer Versuch in %.0f s", name, e, backoff)
                self.stop.wait(backoff)
                backoff = min(backoff * 2, 60.0)

    def run(self) -> None:
        if not self.state.joined:
            raise AgentError("Noch nicht beigetreten")
        log.info("Agent %s läuft für Node „%s“", __version__, self.state.name)
        threads = [
            threading.Thread(target=self._loop, args=("config", self.poll_config, 0), daemon=True),
            threading.Thread(
                target=self._loop,
                args=("status", self.send_status, HEARTBEAT, self.wake),
                daemon=True,
            ),
            threading.Thread(
                target=self._loop, args=("waf", self.waf_round, WAF_EVERY), daemon=True
            ),
        ]
        for t in threads:
            t.start()
        try:
            while not self.stop.is_set():
                self.stop.wait(1.0)
        except KeyboardInterrupt:
            self.stop.set()
        self.wake.set()


def _detail(r: httpx.Response) -> str:
    try:
        return str(r.json().get("detail", r.text))[:500]
    except ValueError:
        return r.text[:500]
