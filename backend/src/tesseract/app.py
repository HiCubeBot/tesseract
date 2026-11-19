"""FastAPI-Anwendung: API unter /api, optional das gebaute Frontend unter /."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tesseract import __version__
from tesseract.api import api_router
from tesseract.auth import LoginThrottle
from tesseract.autoban import AutoBan
from tesseract.bootstrap import init_database, sync_nodes_on_start
from tesseract.config import Settings, get_settings
from tesseract.logs import Collector, Geo
from tesseract.secretbox import load_secretbox


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(), format="%(levelname)s %(name)s: %(message)s"
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.db = init_database(settings)
        app.state.secretbox = load_secretbox(settings)
        from tesseract.notify import Notifier, Sender

        app.state.notifier = Notifier(Sender(app.state.secretbox, app.state.notify_transport))
        tasks = []
        if settings.sync_on_start:
            tasks.append(
                asyncio.create_task(
                    sync_nodes_on_start(app.state.db, settings, app.state.caddy_transport)
                )
            )
        if settings.background_tasks:
            from tesseract.autoban import watch
            from tesseract.nodes import watch_local

            tasks.append(
                asyncio.create_task(
                    watch(
                        app.state.db,
                        settings,
                        app.state.caddy_transport,
                        banner=app.state.autoban,
                        collector=app.state.logs,
                    )
                )
            )
            tasks.append(
                asyncio.create_task(watch_local(app.state.db, settings, app.state.caddy_transport))
            )
            from tesseract.notify import watch as notify_watch

            tasks.append(asyncio.create_task(notify_watch(app.state.db, app.state.notifier)))
            from tesseract.backup import watch as backup_watch

            tasks.append(asyncio.create_task(backup_watch(app)))
            from tesseract.reminders import watch as reminders_watch

            tasks.append(asyncio.create_task(reminders_watch(app.state.db)))
            from tesseract.ldapsync import watch as ldap_watch

            tasks.append(asyncio.create_task(ldap_watch(app)))
            from tesseract.gitmirror import watch as git_watch

            tasks.append(asyncio.create_task(git_watch(app)))
            from tesseract.loki import watch as loki_watch

            tasks.append(asyncio.create_task(loki_watch(app)))
        yield
        for task in tasks:
            task.cancel()
        app.state.db.engine.dispose()

    app = FastAPI(
        title="Tesseract",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.login_throttle = LoginThrottle()
    # Gastseite: falsche Codes pro IP bremsen
    app.state.enroll_throttle = LoginThrottle(limit=10, window=900)
    # Auto-Sperre: Treffer des lokalen Caddy und der Agents zählen gemeinsam
    app.state.autoban = AutoBan()
    # Zentrale Logs: WAF-Zwischenstand pro Node, GeoIP (Phase 5)
    app.state.logs = Collector(Geo(settings.geoip_db))
    # In Tests durch einen httpx.MockTransport ersetzt
    app.state.caddy_transport = None
    # Benachrichtigungen (ntfy, Webhook) – in Tests ein MockTransport
    app.state.notify_transport = None
    # Sicherungen: S3-Ziel in Tests als MockTransport; Sperre fürs Wiederherstellen
    app.state.backup_transport = None
    # Loki (zusätzlicher Log-Speicher) – in Tests ein MockTransport
    app.state.loki_transport = None
    app.state.restore_lock = asyncio.Lock()
    # Aufgaben für Agents (Erreichbarkeit vom Node, Zertifikate des Nodes)
    from tesseract.agent_tasks import TaskBroker

    app.state.agent_tasks = TaskBroker()
    # Admin-Anmeldung per SSO (OIDC) und Passkey
    from tesseract.passkeys import Challenges
    from tesseract.sso import OIDC

    app.state.oidc = OIDC()
    app.state.passkey_challenges = Challenges()
    # LDAP: in Tests eine Mock-Verbindung (ldap3 MOCK_SYNC)
    app.state.ldap_factory = None
    app.include_router(api_router, prefix="/api")
    # Sicherheits-Header und Rate-Limits für öffentliche Endpunkte (Phase 6)
    from tesseract.security import SecurityMiddleware

    app.add_middleware(SecurityMiddleware)
    # Prometheus erwartet /metrics an der Wurzel
    from tesseract.api.metrics import public as metrics_public

    app.include_router(metrics_public)
    # Installationsskript für Nodes: curl -fsSL https://<controller>/install/node.sh | sudo sh
    from tesseract.api.install import router as install_router

    app.include_router(install_router)

    if settings.static_dir and settings.static_dir.is_dir():
        _mount_frontend(app, settings.static_dir)

    return app


def _mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Liefert die Svelte-SPA aus. Das Frontend nutzt einen Hash-Router,
    daher reicht index.html als Fallback für den Wurzelpfad."""
    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index = static_dir / "index.html"

    @app.get("/", include_in_schema=False)
    async def index_html() -> FileResponse:
        return FileResponse(index)

    # Gäste verlängern ihr Gerät selbst: /v liefert dieselbe SPA aus
    @app.get("/v", include_in_schema=False)
    async def renew_page() -> FileResponse:
        return FileResponse(index, headers={"Referrer-Policy": "no-referrer"})

    # Öffentliche Einladungsseite: /e/<token> liefert dieselbe SPA aus
    @app.get("/e/{token}", include_in_schema=False)
    async def enroll_page(token: str) -> FileResponse:
        return FileResponse(index, headers={"Referrer-Policy": "no-referrer"})


def app_factory() -> FastAPI:
    """Für uvicorn --factory bzw. `fastapi dev`."""
    return create_app()
