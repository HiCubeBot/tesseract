"""Einstellungen (Umgebungsvariablen mit Präfix TESSERACT_AGENT_) und gespeicherter Zustand."""

import contextlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Settings:
    data_dir: Path = Path("data")
    # Adresse des Controllers, z. B. https://tesseract.beispiel.de (nur für den Beitritt nötig)
    controller: str = ""
    # Beitritts-Token – alternativ zu `tesseract-agent join --token …`
    join_token: str = ""
    # Admin-API des Caddy auf diesem Node (nie öffentlich)
    caddy_admin_url: str = "http://caddy:2019"
    # Adresse, die in die erzeugte Config geschrieben wird – muss zur caddy_admin_url passen
    caddy_admin_listen: str = "0.0.0.0:2019"
    # Logs von Caddy (gemeinsames Volume); leer = nicht melden
    access_log: Path | None = None
    waf_log: Path | None = None
    # Eigene CA-Datei, falls das Zertifikat des Controllers nicht öffentlich vertraut ist
    controller_ca: Path | None = None
    # Optional: Caddy-Programm, um die Version auszulesen (z. B. bei nativer Installation)
    caddy_bin: str = ""

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        env = dict(os.environ if env is None else env)

        def get(name: str, default: str = "") -> str:
            return env.get(f"TESSERACT_AGENT_{name}", default).strip()

        return cls(
            data_dir=Path(get("DATA_DIR", "data")),
            controller=get("CONTROLLER").rstrip("/"),
            join_token=get("JOIN_TOKEN"),
            caddy_admin_url=get("CADDY_ADMIN_URL", "http://caddy:2019").rstrip("/"),
            caddy_admin_listen=get("CADDY_ADMIN_LISTEN", "0.0.0.0:2019"),
            access_log=Path(p) if (p := get("ACCESS_LOG")) else None,
            waf_log=Path(p) if (p := get("WAF_LOG")) else None,
            controller_ca=Path(p) if (p := get("CONTROLLER_CA")) else None,
            caddy_bin=get("CADDY_BIN"),
        )

    # Dateien im Datenverzeichnis
    @property
    def key_file(self) -> Path:
        return self.data_dir / "node.key"

    @property
    def cert_file(self) -> Path:
        return self.data_dir / "node.crt"

    @property
    def chain_file(self) -> Path:
        return self.data_dir / "chain.pem"

    @property
    def state_file(self) -> Path:
        return self.data_dir / "agent.json"

    @property
    def buffer_file(self) -> Path:
        # Name aus Agent 0.1 beibehalten – ein alter Puffer wird so noch geliefert
        return self.data_dir / "waf-buffer.jsonl"


@dataclass
class State:
    """Was der Agent zwischen Neustarts behält (agent.json)."""

    controller: str = ""
    node_id: int = 0
    name: str = ""
    # Beitritt läuft: Geheimnis zum Abholen des Zertifikats
    join_secret: str = ""
    key_fingerprint: str = ""
    # Nach dem Beitritt
    agent_token: str = ""
    loaded_hash: str = ""
    force: int = 0
    # Lesestand in den Logs (Nachliefern nach einem Neustart)
    waf_offset: int | None = None
    access_offset: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def joined(self) -> bool:
        return bool(self.agent_token)

    @classmethod
    def load(cls, path: Path) -> "State":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.__dict__, indent=2), encoding="utf-8")
        _private(tmp)
        tmp.replace(path)


def _private(path: Path) -> None:
    """Nur für den Besitzer lesbar (auf Windows ohne Wirkung)."""
    with contextlib.suppress(OSError):
        path.chmod(0o600)


def write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    _private(path)
