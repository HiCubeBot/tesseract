"""Beitritt und Arbeitsschleifen des Agents.

- Config:  Long-Polling `GET /api/agent/config` – neue Config wird per `POST /load` in Caddy
           geladen. Caddy rollt bei Fehlern selbst zurück; ohne Controller läuft der letzte
           Stand weiter.
- Rückfall: Der Agent hebt die zuletzt geladene Config auf (`last-config.json`). Startet
           Caddy neu und kommt ohne Config hoch (z. B. weil sein gespeicherter Stand fehlt),
           lädt der Agent diesen Stand wieder – auch wenn der Controller nicht erreichbar ist.
- Status:  alle 30 s (und nach jedem Laden) – laufende Config (Abweichung), Module, Version.
- Logs:    neue Zeilen aus Caddys Zugriffs- und WAF-Log landen erst in einem Puffer auf der
           Platte und werden nachgeliefert, sobald der Controller erreichbar ist.
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
from datetime import UTC, datetime
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
LONG_POLL = 25
HEARTBEAT = 30.0
MODULES_EVERY = 600.0
LOGS_EVERY = 5.0
# so oft prüfen, ob Caddy nach einem Neustart ohne Config läuft
CADDY_CHECK_EVERY = 10.0
# Node-Zertifikat so viele Tage vor Ablauf erneuern
RENEW_DAYS = 60
LOG_BATCH = 1000
LOG_BUFFER_MAX = 200_000


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

    def metrics(self) -> str:
        """Nur die caddy_*-Zeilen aus GET /metrics."""
        r = self.http.get("/metrics")
        r.raise_for_status()
        keep = [
            line
            for line in r.text.splitlines()
            if line.startswith(("caddy_", "# HELP caddy_", "# TYPE caddy_"))
        ]
        return chr(10).join(keep)

    def modules(self) -> list[str]:
        found = []
        for name, caddyfile in MODULE_PROBES.items():
            r = self.http.post(
                "/adapt", content=caddyfile, headers={"Content-Type": "text/caddyfile"}
            )
            if r.status_code < 400:
                found.append(name)
        return found


def read_containers(docker_host: str, transport: httpx.BaseTransport | None = None) -> list:
    """Container mit tesseract.*-Labels über die Docker-API (auch gestoppte)."""
    if transport is not None:
        client = httpx.Client(transport=transport, base_url="http://docker", timeout=10.0)
    elif docker_host.startswith("unix://"):
        client = httpx.Client(
            transport=httpx.HTTPTransport(uds=docker_host.removeprefix("unix://")),
            base_url="http://docker",
            timeout=10.0,
        )
    else:
        url = docker_host.replace("tcp://", "http://", 1)
        client = httpx.Client(base_url=url.rstrip("/"), timeout=10.0)
    with client:
        r = client.get(
            "/containers/json",
            params={"all": "true", "filters": json.dumps({"label": ["tesseract.domain"]})},
        )
    r.raise_for_status()
    out = []
    for c in r.json():
        out.append(
            {
                "id": str(c.get("Id", ""))[:12],
                "name": (c.get("Names") or [""])[0].lstrip("/"),
                "state": c.get("State") or "",
                "labels": {
                    k: v for k, v in (c.get("Labels") or {}).items() if k.startswith("tesseract.")
                },
                "ports": sorted(
                    {p["PrivatePort"] for p in c.get("Ports") or [] if p.get("Type") == "tcp"}
                ),
            }
        )
    return out


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


# ---------- Aufgaben vom Controller (ab 1.1) ----------


def task_tcp(params: dict[str, Any]) -> dict[str, Any]:
    """Ist das Ziel eines Hosts vom Node aus erreichbar?"""
    host, port = str(params["host"]), int(params["port"])
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=float(params.get("timeout", 3))):
            pass
    except OSError as e:
        return {"ok": False, "error": e.strerror or str(e) or type(e).__name__}
    return {"ok": True, "ms": round((time.perf_counter() - start) * 1000)}


def tls_address(settings: Settings) -> tuple[str, int]:
    if settings.caddy_tls_address:
        host, _, port = settings.caddy_tls_address.rpartition(":")
        return host.strip("[]") or settings.caddy_tls_address, int(port) if port.isdigit() else 443
    from urllib.parse import urlsplit

    return urlsplit(settings.caddy_admin_url).hostname or "127.0.0.1", 443


def task_certs(params: dict[str, Any], address: tuple[str, int]) -> dict[str, Any]:
    """Welches Zertifikat liefert der eigene Caddy für jeden Namen aus? (DER, Base64)"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    out: dict[str, Any] = {}
    for name in [str(n) for n in params.get("names", [])][:500]:
        try:
            with (
                socket.create_connection(address, timeout=4) as raw,
                ctx.wrap_socket(raw, server_hostname=name) as s,
            ):
                der = s.getpeercert(binary_form=True)
            out[name] = (
                {"der": base64.b64encode(der).decode()} if der else {"error": "kein Zertifikat"}
            )
        except (OSError, ssl.SSLError) as e:
            out[name] = {"error": str(e) or type(e).__name__}
    return {"certs": out}


# ---------- Logs ----------


def _tail(path: Path | None, offset: int | None) -> tuple[list[str], int | None]:
    """Neue vollständige Zeilen ab `offset`. Erster Aufruf (None) springt ans Ende."""
    if path is None:
        return [], offset
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return [], offset
    if offset is None:
        return [], size
    if size < offset:
        offset = 0  # rotiert
    if size == offset:
        return [], offset
    with path.open("rb") as f:
        f.seek(offset)
        data = f.read(8 * 1024 * 1024)
    cut = data.rfind(b"\n") + 1
    lines = [x for x in data[:cut].decode("utf-8", "replace").splitlines() if x.strip()]
    return lines, offset + cut


class LogShipper:
    """Liest neue Zeilen aus Zugriffs- und WAF-Log in einen Puffer auf der Platte und liefert
    sie aus. Ist der Controller weg, bleibt der Puffer liegen (höchstens LOG_BUFFER_MAX Zeilen,
    die ältesten fallen zuerst weg)."""

    def __init__(self, access_log: Path | None, waf_log: Path | None, buffer: Path) -> None:
        self.access_log = access_log
        self.waf_log = waf_log
        self.buffer = buffer

    def collect(self, state: State) -> int:
        access, state.access_offset = _tail(self.access_log, state.access_offset)
        waf, state.waf_offset = _tail(self.waf_log, state.waf_offset)
        items = [json.dumps({"k": "a", "l": x}) for x in access]
        items += [json.dumps({"k": "w", "l": x}) for x in waf]
        if items:
            self.buffer.parent.mkdir(parents=True, exist_ok=True)
            with self.buffer.open("a", encoding="utf-8") as f:
                f.writelines(i + "\n" for i in items)
            self._trim()
        return len(items)

    def _trim(self) -> None:
        lines = self._raw()
        if len(lines) > LOG_BUFFER_MAX:
            self._write(lines[-LOG_BUFFER_MAX:])

    def _raw(self) -> list[str]:
        if not self.buffer.exists():
            return []
        return [x for x in self.buffer.read_text(encoding="utf-8").splitlines() if x]

    @staticmethod
    def _decode(raw: str) -> tuple[str, str]:
        try:
            item = json.loads(raw)
            if isinstance(item, dict) and "k" in item:
                return item["k"], item["l"]
        except ValueError:
            pass
        return "w", raw  # Puffer von Agent 0.1: nur WAF-Zeilen

    def pending(self) -> list[tuple[str, str]]:
        return [self._decode(x) for x in self._raw()]

    def _write(self, lines: list[str]) -> None:
        tmp = self.buffer.with_suffix(".tmp")
        tmp.write_text("".join(x + "\n" for x in lines), encoding="utf-8")
        tmp.replace(self.buffer)

    def ship(self, send) -> int:
        """Puffer in Paketen senden; was nicht ankommt, bleibt liegen."""
        raw = self._raw()
        sent = 0
        while sent < len(raw):
            batch = [self._decode(x) for x in raw[sent : sent + LOG_BATCH]]
            send([line for k, line in batch if k == "a"], [line for k, line in batch if k == "w"])
            sent = min(sent + LOG_BATCH, len(raw))
            self._write(raw[sent:])
        return sent


# ---------- Agent ----------


class Agent:
    def __init__(
        self,
        settings: Settings,
        controller_transport: httpx.BaseTransport | None = None,
        caddy_transport: httpx.BaseTransport | None = None,
        docker_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self._docker_transport = docker_transport
        self.state = State.load(settings.state_file)
        self._controller_transport = controller_transport
        self.caddy = Caddy(settings.caddy_admin_url, caddy_transport)
        self.logs = LogShipper(settings.access_log, settings.waf_log, settings.buffer_file)
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.load_error: str | None = None
        self.rejected_hash = ""
        # Will der Controller die Caddy-Metriken? (kommt mit der Antwort auf den Status)
        self.want_metrics = False
        # Controller verlangt ein neues Zertifikat (nach einem Wechsel der CA)
        self.renew_requested = False
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
        params = {"known": known, "force": self.state.force, "wait": wait, "tasks": 1}
        with self._http(with_cert=True, timeout=wait + 15) as c:
            r = c.get("/api/agent/config", params=params)
        if r.status_code == 204:
            return False
        if r.status_code != 200:
            raise AgentError(f"Config abholen fehlgeschlagen ({r.status_code}): {_detail(r)}")
        data = r.json()
        if data.get("tasks"):
            for task in data["tasks"]:
                threading.Thread(target=self.run_task, args=(task,), daemon=True).start()
        # Nur Aufgaben, Config unverändert
        if data.get("config") is None or (
            data["hash"] == self.state.loaded_hash and data["force"] == self.state.force
        ):
            return False
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
        self.remember(data["config"])
        self.load_error = None
        self.rejected_hash = ""
        self.state.loaded_hash = data["hash"]
        self.state.force = data["force"]
        self.save()
        log.info("Neue Config geladen (%s)", data["hash"][:12])
        self.wake.set()
        return True

    # --- Letzter Stand ohne Controller ---

    def remember(self, config: dict[str, Any]) -> None:
        """Geladene Config im eigenen Datenverzeichnis aufheben (nur für den Besitzer lesbar)."""
        raw = json.dumps(config, separators=(",", ":")).encode()
        tmp = self.settings.last_config_file.with_suffix(".tmp")
        write_private(tmp, raw)
        tmp.replace(self.settings.last_config_file)

    def ensure_config(self) -> bool:
        """Läuft Caddy ohne Config (nur Admin-API, keine Apps), den zuletzt geladenen Stand
        wieder laden – unabhängig vom Controller. True, wenn geladen wurde.

        Normalerweise sorgt schon Caddys `--resume` dafür; das hier greift, wenn dessen
        gespeicherter Stand fehlt (Volume neu, Caddy ohne --resume gestartet …)."""
        if not self.state.loaded_hash:
            return False
        running = self.caddy.running()
        path = self.settings.last_config_file
        if running.get("apps"):
            # Agent älter als diese Funktion: laufenden Stand einmalig übernehmen
            if not path.exists() and config_hash(running) == self.state.loaded_hash:
                self.remember(running)
            return False
        if not path.exists():
            log.warning("Caddy läuft ohne Config, und es gibt keinen gespeicherten Stand")
            return False
        config = json.loads(path.read_text(encoding="utf-8"))
        self.caddy.load(config)
        log.warning(
            "Caddy lief ohne Config – letzten bekannten Stand (%s) wieder geladen",
            config_hash(config)[:12],
        )
        self.wake.set()
        return True

    # --- Status ---

    def status_report(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "agent_version": __version__,
            "caddy_version": self._version,
            "admin_listen": self.settings.caddy_admin_listen,
            "controller": self.state.controller or self.settings.controller or None,
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
            if self.want_metrics:
                report["caddy_metrics"] = self.caddy.metrics()
        except httpx.HTTPError as e:
            report["load_error"] = self.load_error or f"Caddy nicht erreichbar: {e}"
        if self.settings.docker_host or self._docker_transport:
            try:
                report["containers"] = read_containers(
                    self.settings.docker_host, self._docker_transport
                )
            except (httpx.HTTPError, ValueError) as e:
                report["docker_error"] = (str(e) or e.__class__.__name__)[:1000]
        return report

    def run_task(self, task: dict[str, Any]) -> None:
        kind, params = task.get("kind"), task.get("params") or {}
        try:
            if kind == "tcp":
                result = task_tcp(params)
            elif kind == "certs":
                result = task_certs(params, tls_address(self.settings))
            else:
                result = {"ok": False, "error": f"unbekannte Aufgabe {kind}"}
        except Exception as e:  # noqa: BLE001 – Ergebnis statt Absturz
            result = {"ok": False, "error": str(e)}
        try:
            with self._http(with_cert=True) as c:
                c.post(f"/api/agent/tasks/{task['id']}", json={"result": result})
        except httpx.HTTPError as e:
            log.warning("Ergebnis der Aufgabe %s nicht gesendet: %s", kind, e)

    def cert_days_left(self) -> float | None:
        try:
            cert = x509.load_pem_x509_certificate(self.settings.cert_file.read_bytes())
        except (OSError, ValueError):
            return None
        return (cert.not_valid_after_utc - datetime.now(UTC)).total_seconds() / 86400

    def renew_if_due(self) -> bool:
        """Neuen Schlüssel erzeugen und das Zertifikat erneuern lassen, solange das alte
        noch gilt. Erst nach Erfolg werden Schlüssel und Zertifikat ersetzt."""
        left = self.cert_days_left()
        if left is None or (left > RENEW_DAYS and not self.renew_requested):
            return False
        key = ec.generate_private_key(ec.SECP256R1())
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, self.state.name)]))
            .sign(key, hashes.SHA256())
        )
        with self._http(with_cert=True) as c:
            r = c.post(
                "/api/agent/renew",
                json={"csr": csr.public_bytes(serialization.Encoding.PEM).decode()},
            )
        if r.status_code != 200:
            raise AgentError(f"Zertifikat erneuern fehlgeschlagen ({r.status_code}): {_detail(r)}")
        data = r.json()
        with self.lock:
            key_tmp = self.settings.key_file.with_name(self.settings.key_file.name + ".new")
            write_private(
                key_tmp,
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ),
            )
            cert_tmp = self.settings.cert_file.with_name(self.settings.cert_file.name + ".new")
            cert_tmp.write_text(data["cert_pem"], encoding="utf-8")
            key_tmp.replace(self.settings.key_file)
            cert_tmp.replace(self.settings.cert_file)
            self.settings.chain_file.write_text(data["chain_pem"], encoding="utf-8")
        self.renew_requested = False
        log.info("Node-Zertifikat erneuert, gültig bis %s", data.get("not_after"))
        return True

    def send_status(self) -> None:
        self.renew_if_due()
        with self._http(with_cert=True) as c:
            r = c.post("/api/agent/status", json=self.status_report())
        if r.status_code != 200:
            raise AgentError(f"Status senden fehlgeschlagen ({r.status_code}): {_detail(r)}")
        try:
            answer = r.json()
        except ValueError:
            answer = {}
        self.want_metrics = bool(answer.get("caddy_metrics"))
        if answer.get("renew_cert") and not self.renew_requested:
            log.info("Controller hat eine neue CA – Zertifikat wird erneuert")
            self.renew_requested = True
            self.wake.set()

    def send_logs(self, access: list[str], waf: list[str]) -> None:
        with self._http(with_cert=True) as c:
            r = c.post("/api/agent/logs", json={"access": access, "waf": waf})
        if r.status_code != 200:
            raise AgentError(f"Logs senden fehlgeschlagen ({r.status_code})")

    def logs_round(self) -> int:
        with self.lock:
            self.logs.collect(self.state)
            self.state.save(self.settings.state_file)
        return self.logs.ship(self.send_logs)

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
            threading.Thread(
                target=self._loop,
                args=("caddy", self.ensure_config, CADDY_CHECK_EVERY),
                daemon=True,
            ),
            threading.Thread(target=self._loop, args=("config", self.poll_config, 0), daemon=True),
            threading.Thread(
                target=self._loop,
                args=("status", self.send_status, HEARTBEAT, self.wake),
                daemon=True,
            ),
            threading.Thread(
                target=self._loop, args=("logs", self.logs_round, LOGS_EVERY), daemon=True
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
