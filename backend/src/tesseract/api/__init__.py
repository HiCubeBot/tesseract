"""Alle API-Router. Neue Bereiche hier einhängen."""

from fastapi import APIRouter

from tesseract.api import audit, auth, health, hosts, nodes, settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(audit.router)
api_router.include_router(hosts.router)
api_router.include_router(nodes.router)
api_router.include_router(settings.router)
