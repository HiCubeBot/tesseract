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
from tesseract.bootstrap import init_database, sync_nodes_on_start
from tesseract.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(), format="%(levelname)s %(name)s: %(message)s"
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.db = init_database(settings)
        task = None
        if settings.sync_on_start:
            task = asyncio.create_task(
                sync_nodes_on_start(app.state.db, settings, app.state.caddy_transport)
            )
        yield
        if task:
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
    # In Tests durch einen httpx.MockTransport ersetzt
    app.state.caddy_transport = None
    app.include_router(api_router, prefix="/api")

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


def app_factory() -> FastAPI:
    """Für uvicorn --factory bzw. `fastapi dev`."""
    return create_app()
