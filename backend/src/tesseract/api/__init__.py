"""Alle API-Router. Neue Bereiche hier einhängen."""

from fastapi import APIRouter

from tesseract.api import (
    access,
    agent,
    audit,
    auth,
    backups,
    bans,
    ca,
    certificates,
    customcerts,
    health,
    hosts,
    invites,
    iplists,
    logs,
    metrics,
    nodes,
    notify,
    people,
    settings,
    stats,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(audit.router)
api_router.include_router(hosts.router)
api_router.include_router(nodes.router)
api_router.include_router(settings.router)
api_router.include_router(ca.router)
api_router.include_router(people.router)
api_router.include_router(access.router)
api_router.include_router(invites.admin)
api_router.include_router(invites.public)
api_router.include_router(iplists.router)
api_router.include_router(bans.router)
api_router.include_router(certificates.router)
api_router.include_router(customcerts.router)
api_router.include_router(agent.router)
api_router.include_router(logs.router)
api_router.include_router(stats.router)
api_router.include_router(metrics.router)
api_router.include_router(notify.router)
api_router.include_router(backups.router)
