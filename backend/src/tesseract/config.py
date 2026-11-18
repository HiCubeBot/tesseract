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

    # Gebautes Frontend (frontend/dist). Fehlt der Ordner, läuft nur die API.
    static_dir: Path | None = None

    # Admin-API von Caddy (Phase 1: lokaler Caddy im Compose-Stack)
    caddy_admin_url: str = "http://caddy:2019"

    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
