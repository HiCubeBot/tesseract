"""Statistik (Phase 5): Sicherheit, Traffic & Leistung, Nutzung."""

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status

from tesseract import stats, stats_external
from tesseract.deps import DB, CurrentActor
from tesseract.logstore import StoreError, store_for
from tesseract.services import get_general

router = APIRouter(prefix="/stats", tags=["stats"])

Range = Literal["24h", "7d", "30d"]


def _store(request: Request, db):
    return store_for(get_general(db), getattr(request.app.state, "loki_transport", None))


def _external(fn, *args) -> dict[str, Any]:
    try:
        return {**fn(*args), "source": "external"}
    except StoreError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e


@router.get("/security")
def security(
    request: Request, db: DB, _: CurrentActor, range: Range = "24h", node: str = ""
) -> dict[str, Any]:
    store = _store(request, db)
    data = (
        _external(stats_external.security, store, range, node or None)
        if store
        else stats.security(db, range, node or None)
    )
    from tesseract.geoip import status as geoip_status

    return {
        **data,
        "geoip": request.app.state.logs.geo.ready,
        # Quellenangabe (DB-IP verlangt sie bei Weitergabe von Auswertungen)
        "geoip_attribution": geoip_status(request.app)["attribution"],
    }


@router.get("/traffic")
def traffic(
    request: Request, db: DB, _: CurrentActor, range: Range = "24h", node: str = ""
) -> dict[str, Any]:
    store = _store(request, db)
    if store:
        return _external(stats_external.traffic, store, range, node or None)
    return stats.traffic(db, range, node or None)


@router.get("/usage")
def usage(request: Request, db: DB, _: CurrentActor, range: Range = "7d") -> dict[str, Any]:
    store = _store(request, db)
    if store:
        return _external(stats_external.usage, db, store, range)
    return stats.usage(db, range)
