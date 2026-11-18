"""FastAPI-Anwendung: API unter /api, optional das gebaute Frontend unter /."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tesseract import __version__
from tesseract.api import api_router
from tesseract.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title="Tesseract",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
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


app = create_app()
