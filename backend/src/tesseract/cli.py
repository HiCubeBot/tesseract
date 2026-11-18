"""Kommandozeile: startet den Controller mit uvicorn."""

import uvicorn

from tesseract.config import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "tesseract.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level,
        proxy_headers=True,
    )
