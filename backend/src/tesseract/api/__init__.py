"""Alle API-Router. Neue Bereiche (hosts, users, devices, nodes …) hier einhängen."""

from fastapi import APIRouter

from tesseract.api import health

api_router = APIRouter()
api_router.include_router(health.router)
