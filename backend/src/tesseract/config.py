"""Konfiguration über Umgebungsvariablen (Präfix `TESSERACT_`)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TESSERACT_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False

    # Persistente Daten des Controllers (DB, CA-Zwischenzertifikat, Backups …)
    data_dir: Path = Path("data")

    # Datenbank-URL; leer = SQLite-Datei im data_dir
    database_url: str = ""

    # Gebautes Frontend (frontend/dist). Fehlt der Ordner, läuft nur die API.
    static_dir: Path | None = None

    # Admin-API von Caddy (Phase 1: lokaler Caddy im Compose-Stack)
    caddy_admin_url: str = "http://caddy:2019"
    # Adresse, auf der Caddys Admin-API nach dem Laden der Config lauschen soll.
    # Muss zur caddy_admin_url passen, sonst sperrt sich der Controller aus.
    caddy_admin_listen: str = "0.0.0.0:2019"
    # Domain der Tesseract-Oberfläche; Caddy bekommt dafür immer eine eigene Route
    controller_domain: str = ""
    # Wie Caddy den Controller selbst erreicht (Route für die Controller-Domain)
    controller_upstream: str = "tesseract:8000"

    # Session-Cookie nur über HTTPS senden (für lokale Entwicklung abschalten)
    cookie_secure: bool = True
    session_hours: int = 12
    session_remember_days: int = 30

    # Beim Start die Config an alle Nodes übertragen
    sync_on_start: bool = True

    log_level: str = "info"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'tesseract.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
