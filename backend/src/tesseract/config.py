"""Konfiguration über Umgebungsvariablen (Präfix `TESSERACT_`)."""

import ipaddress
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TESSERACT_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    # Von wem X-Forwarded-For übernommen wird (Caddy davor). Standard: private Netze – im
    # Compose-Stack ist das Caddy. Ohne das sähe der Controller nur Caddys IP: Anmelde-Bremse
    # und Audit-Log wären falsch. Den Port des Controllers nie direkt veröffentlichen.
    forwarded_allow_ips: str = "127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7"
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
    # Wo der Controller Caddys HTTPS-Port erreicht (Zertifikatsübersicht);
    # leer = Host der Admin-URL mit Port 443
    caddy_tls_address: str = ""
    # Wie Caddy den Controller selbst erreicht (Route für die Controller-Domain)
    controller_upstream: str = "tesseract:8000"

    # Admin-Zugang aus der Umgebung. Ist ein Passwort gesetzt, gilt es bei jedem Start
    # (in der Oberfläche lässt es sich dann nicht ändern). Leer = Zufallspasswort beim ersten
    # Start, steht einmalig im Log. *_FILE liest es aus einer Datei (Docker-Secrets).
    admin_username: str = "admin"
    # Aus welchen Netzen die Oberfläche erreichbar ist (kommagetrennt, CIDR). Aus anderen Netzen
    # bricht Caddy die Verbindung ab. Einladungen, Gerät verlängern und die Agent-Schnittstelle
    # bleiben überall erreichbar. Standard: alle Netze.
    admin_networks: str = "0.0.0.0/0,::/0"
    # Node-Schnittstelle (/api/agent/…, Installationsskript) von admin_networks ausnehmen, damit
    # Nodes aus jedem Netz den Controller erreichen. Aus = auch Nodes nur aus admin_networks.
    agent_api_public: bool = True
    admin_password: str = ""
    admin_password_file: Path | None = None

    # Startwerte für Einstellungen der Oberfläche. Gesetzt = gilt bei jedem Start
    # (überschreibt, was in der Oberfläche eingestellt wurde).
    acme_email: str | None = None
    logs_days: int | None = None
    # Loki-URL, z. B. http://loki:3100 (Compose-Profil „loki“)
    loki_url: str | None = None
    # "loki" oder "victorialogs" – Art des Log-Speichers hinter der URL
    loki_kind: str | None = None
    # Log-Ansicht und Statistik aus Loki/VictoriaLogs lesen (statt SQLite)
    logs_external: bool | None = None
    # Netze, kommagetrennt (z. B. "192.168.178.0/24,10.8.0.0/24")
    internal_networks: str | None = None
    trusted_proxies: str | None = None
    # Cloudflare-API-Token für DNS-01 (auch für das Zertifikat der Oberfläche selbst).
    # Gesetzt = gilt bei jedem Start, in der Oberfläche gesperrt. *_FILE: aus einer Datei.
    cloudflare_token: str | None = None
    cloudflare_token_file: Path | None = None

    # Session-Cookie nur über HTTPS senden (für lokale Entwicklung abschalten)
    cookie_secure: bool = True
    session_hours: int = 12
    session_remember_days: int = 30

    # Hauptschlüssel (Base64, 32 Byte) für verschlüsselte Geheimnisse; leer = data_dir/secret.key
    secret_key: str = ""

    # Beim Start die Config an alle Nodes übertragen
    sync_on_start: bool = True

    # WAF-Log für die Auto-Sperre: Pfad im Caddy-Container und Pfad, unter dem der
    # Controller dieselbe Datei liest (gemeinsames Volume). Leer = Auto-Sperre ohne Daten.
    caddy_waf_log: str = ""
    waf_log_path: Path | None = None
    # Zugriffs-Log (Phase 5): Pfad im Caddy-Container und Pfad, unter dem der Controller
    # dieselbe Datei liest. Leer = keine Logs vom lokalen Node.
    caddy_access_log: str = ""
    access_log_path: Path | None = None
    # Optionale GeoIP-Datenbank (MaxMind GeoLite2-Country o. ä., .mmdb) für Länder in Logs/Statistik
    geoip_db: Path | None = None
    # GeoIP-Datenbank automatisch holen und monatlich erneuern: "dbip" (DB-IP Lite, ohne Konto).
    # Leer = aus (keine Anfrage nach außen, Datei kommt aus geoip_db)
    geoip_auto: str = ""
    # Optionale ASN-Datenbank (.mmdb, z. B. GeoLite2-ASN) für die Netzbetreiber
    geoip_asn_db: Path | None = None
    # Ordner für lokale Sicherungen; leer = data_dir/backups
    backup_dir: Path | None = None
    # Docker-API des lokalen Nodes für Hosts aus Container-Labels, z. B.
    # tcp://docker-socket-proxy:2375 oder unix:///var/run/docker.sock; leer = aus
    docker_host: str = ""
    # restic für das Sicherungsziel „Restic“ (im Docker-Image enthalten)
    restic_bin: str = "restic"
    # Hintergrundaufgaben (Auto-Sperre); in Tests aus
    background_tasks: bool = True

    log_level: str = "info"

    @property
    def resolved_admin_password(self) -> str:
        if self.admin_password_file:
            return self.admin_password_file.read_text(encoding="utf-8").strip()
        return self.admin_password

    @field_validator("geoip_auto")
    @classmethod
    def _geoip_auto(cls, v: str) -> str:
        v = v.strip().lower()
        if v in ("", "off", "aus", "false", "0"):
            return ""
        parts = [x for x in v.replace("+", ",").replace(" ", "").split(",") if x]
        if parts[0] not in ("dbip", "dbip-city") or any(x != "asn" for x in parts[1:]):
            raise ValueError(
                "TESSERACT_GEOIP_AUTO: „dbip“ (Länder) oder „dbip-city“ (Städte), "
                "wahlweise mit „+asn“, oder leer"
            )
        return ",".join([parts[0], *(["asn"] if "asn" in parts[1:] else [])])

    @field_validator("admin_networks")
    @classmethod
    def _admin_networks(cls, v: str) -> str:
        nets = [x.strip() for x in v.replace(";", ",").split(",") if x.strip()]
        if not nets:
            raise ValueError("TESSERACT_ADMIN_NETWORKS: mindestens ein Netz angeben")
        for n in nets:
            try:
                ipaddress.ip_network(n, strict=False)
            except ValueError as e:
                raise ValueError(f"TESSERACT_ADMIN_NETWORKS: „{n}“ ist kein Netz") from e
        return ",".join(nets)

    @property
    def admin_network_list(self) -> list[str]:
        """Netze normalisiert (z. B. 192.168.1.5/24 → 192.168.1.0/24)."""
        return [
            str(ipaddress.ip_network(n, strict=False)) for n in self.admin_networks.split(",") if n
        ]

    @property
    def admin_networks_open(self) -> bool:
        """Alle Netze erlaubt (IPv4 und IPv6) – dann braucht Caddy keine Prüfung."""
        nets = set(self.admin_network_list)
        return "0.0.0.0/0" in nets and "::/0" in nets

    @property
    def resolved_cloudflare_token(self) -> str:
        if self.cloudflare_token_file:
            return self.cloudflare_token_file.read_text(encoding="utf-8").strip()
        return (self.cloudflare_token or "").strip()

    def env_managed(self) -> list[str]:
        """Namen der Einstellungen, die aus der Umgebung kommen (für die Oberfläche)."""
        names = list(self.env_overrides())
        if self.resolved_cloudflare_token:
            names.append("cloudflare_token")
        return sorted(names)

    def env_overrides(self) -> dict:
        """Einstellungen der Oberfläche, die aus der Umgebung festgelegt sind."""
        out: dict = {}
        if self.acme_email is not None:
            out["acme_email"] = self.acme_email.strip()
        if self.logs_days is not None:
            out["logs_days"] = max(1, min(365, self.logs_days))
        if self.loki_url:
            out["loki_url"] = self.loki_url.strip()
        if self.loki_kind and self.loki_kind.strip().lower() in ("loki", "victorialogs"):
            out["loki_kind"] = self.loki_kind.strip().lower()
        if self.logs_external is not None:
            out["logs_external"] = self.logs_external
        for key in ("internal_networks", "trusted_proxies"):
            raw = getattr(self, key)
            if raw is not None:
                out[key] = [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]
        return out

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'tesseract.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
