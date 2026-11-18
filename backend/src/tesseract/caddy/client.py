"""Überträgt Configs an die Admin-API von Caddy."""

from typing import Any

import httpx


class CaddyError(Exception):
    pass


class CaddyClient:
    def __init__(self, admin_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self.admin_url = admin_url.rstrip("/")
        self._transport = transport

    def _client(self) -> httpx.Client:
        # Caddy prüft bei der Admin-API den Origin; ohne Header ist das unkritisch.
        return httpx.Client(base_url=self.admin_url, timeout=15.0, transport=self._transport)

    def load(self, config: dict[str, Any]) -> None:
        """Ersetzt die laufende Config (POST /load). Caddy rollt bei Fehlern selbst zurück."""
        try:
            with self._client() as c:
                r = c.post("/load", json=config)
        except httpx.HTTPError as e:
            raise CaddyError(f"Caddy nicht erreichbar ({self.admin_url}): {e}") from e
        if r.status_code >= 400:
            raise CaddyError(_error_text(r))

    def current_config(self) -> dict[str, Any] | None:
        try:
            with self._client() as c:
                r = c.get("/config/")
        except httpx.HTTPError as e:
            raise CaddyError(f"Caddy nicht erreichbar ({self.admin_url}): {e}") from e
        if r.status_code >= 400:
            raise CaddyError(_error_text(r))
        return r.json()

    def pki(self, ca: str = "local") -> dict[str, Any]:
        """Infos zu Caddys eigener CA (GET /pki/ca/<id>), u. a. root_certificate."""
        try:
            with self._client() as c:
                r = c.get(f"/pki/ca/{ca}")
        except httpx.HTTPError as e:
            raise CaddyError(f"Caddy nicht erreichbar ({self.admin_url}): {e}") from e
        if r.status_code >= 400:
            raise CaddyError(_error_text(r))
        return r.json()

    def metrics(self) -> str:
        """Prometheus-Text der Admin-API (GET /metrics)."""
        try:
            with self._client() as c:
                r = c.get("/metrics")
        except httpx.HTTPError as e:
            raise CaddyError(f"Caddy nicht erreichbar ({self.admin_url}): {e}") from e
        if r.status_code >= 400:
            raise CaddyError(_error_text(r))
        return r.text

    def adapt_ok(self, caddyfile: str) -> bool:
        """Lässt Caddy ein Caddyfile nur übersetzen (POST /adapt, nichts wird geladen).
        False, wenn der Adapter es ablehnt – z. B. weil ein Modul fehlt."""
        try:
            with self._client() as c:
                r = c.post("/adapt", content=caddyfile, headers={"Content-Type": "text/caddyfile"})
        except httpx.HTTPError as e:
            raise CaddyError(f"Caddy nicht erreichbar ({self.admin_url}): {e}") from e
        return r.status_code < 400


def _error_text(r: httpx.Response) -> str:
    try:
        return f"Caddy {r.status_code}: {r.json().get('error', r.text)}"
    except ValueError:
        return f"Caddy {r.status_code}: {r.text[:500]}"
