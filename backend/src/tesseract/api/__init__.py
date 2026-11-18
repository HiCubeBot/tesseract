"""Alle API-Router. Neue Bereiche hier einhängen."""

from fastapi import APIRouter

from tesseract.api import audit, auth, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(audit.router)
