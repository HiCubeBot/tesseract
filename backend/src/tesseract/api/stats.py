"""Statistik (Phase 5): Sicherheit, Traffic & Leistung, Nutzung."""

from typing import Any, Literal

from fastapi import APIRouter, Request

from tesseract import stats
from tesseract.deps import DB, CurrentActor

router = APIRouter(prefix="/stats", tags=["stats"])

Range = Literal["24h", "7d", "30d"]


@router.get("/security")
def security(
    request: Request, db: DB, _: CurrentActor, range: Range = "24h", node: str = ""
) -> dict[str, Any]:
    return {
        **stats.security(db, range, node or None),
        "geoip": request.app.state.logs.geo.ready,
    }


@router.get("/traffic")
def traffic(db: DB, _: CurrentActor, range: Range = "24h", node: str = "") -> dict[str, Any]:
    return stats.traffic(db, range, node or None)


@router.get("/usage")
def usage(db: DB, _: CurrentActor, range: Range = "7d") -> dict[str, Any]:
    return stats.usage(db, range)
