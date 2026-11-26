"""Statistik (Phase 5): Sicherheit, Traffic & Leistung, Nutzung."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status

from tesseract import stats, stats_external, statsview
from tesseract.deps import DB, CurrentActor
from tesseract.logstore import StoreError, store_for
from tesseract.services import get_general

router = APIRouter(prefix="/stats", tags=["stats"])

Range = Literal["24h", "7d", "30d"]
RangeAll = Literal["24h", "7d", "30d", "all"]


def _store(request: Request, db):
    return store_for(get_general(db), getattr(request.app.state, "loki_transport", None))


def _run(fn, *args) -> dict[str, Any]:
    try:
        return fn(*args)
    except StoreError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e


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
    from tesseract.deps import client_ip
    from tesseract.geoip import status as geoip_status
    from tesseract.services import resolve_ranges

    g = get_general(db)
    internal = resolve_ranges(db, g["internal_networks"], g["internal_list_ids"])
    extra = _run(
        statsview.security_extra,
        _any_store(request, db),
        db,
        range,
        node or None,
        client_ip(request),
        internal,
    )
    return {
        **data,
        **extra,
        "geoip": request.app.state.logs.geo.ready,
        # Quellenangabe (DB-IP verlangt sie bei Weitergabe von Auswertungen)
        "geoip_attribution": geoip_status(request.app)["attribution"],
    }


@router.get("/traffic")
def traffic(
    request: Request, db: DB, _: CurrentActor, range: RangeAll = "24h", node: str = ""
) -> dict[str, Any]:
    if range == "all":
        # gesamter Zeitraum aus den verdichteten Tageswerten (immer aus SQLite)
        return {"range": "all", **statsview.traffic_all(db, node or None)}
    store = _store(request, db)
    if store:
        data = _external(stats_external.traffic, store, range, node or None)
    else:
        data = stats.traffic(db, range, node or None)
    extra = _run(statsview.traffic_extra, _any_store(request, db), range, node or None)
    return {**data, **extra, "range": range}


@router.get("/geo")
def geo(
    request: Request,
    db: DB,
    _: CurrentActor,
    range: Range = "24h",
    node: str = "",
    which: Literal["all", "denied", "allowed"] = "all",
    country: Annotated[str, Query(pattern=r"^([A-Za-z]{2})?$")] = "",
) -> dict[str, Any]:
    """Herkunft für die Karte: Länder, Städte (mit Stadt-Datenbank), Netzbetreiber (mit ASN).
    Mit `country` (ISO-Code) nur Städte und Netzbetreiber dieses Landes plus Zusammenfassung."""
    from tesseract.geoip import status as geoip_status

    data = _run(
        statsview.geo,
        _any_store(request, db),
        range,
        node or None,
        which,
        country.upper() or None,
    )
    g = request.app.state.logs.geo
    return {
        **data,
        "geoip": g.ready,
        "cities_db": g.cities,
        "asn_db": g.asn,
        "geoip_attribution": geoip_status(request.app)["attribution"],
    }


@router.get("/records")
def records(db: DB, _: CurrentActor) -> dict[str, Any]:
    """Rekorde seit Beginn der Aufzeichnung (aus den Tages- und Stundenwerten)."""
    return statsview.records(db)


@router.get("/bots")
def bots(db: DB, _: CurrentActor, range: Range = "24h", node: str = "") -> dict[str, Any]:
    """Bot-Schutz (Anubis): Prüfungen, Abweisungen, bestanden – immer aus der eigenen Datenbank."""
    from tesseract import botstats

    return {
        **botstats.bots(db, range, node or None),
        "anubis": bool(get_general(db)["anubis_url"]),
    }


@router.get("/usage")
def usage(request: Request, db: DB, _: CurrentActor, range: Range = "7d") -> dict[str, Any]:
    store = _store(request, db)
    if store:
        return _external(stats_external.usage, db, store, range)
    return stats.usage(db, range)


@router.get("/countries")
def countries(
    request: Request,
    db: DB,
    _: CurrentActor,
    range: Range = "24h",
    node: str = "",
    which: Literal["all", "denied", "allowed"] = "all",
) -> dict[str, Any]:
    """Herkunft der Anfragen für die Karte: alle, nur abgelehnte oder nur angenommene."""
    store = _store(request, db)
    data = (
        _external(stats_external.countries, store, range, node or None, which)
        if store
        else stats.countries(db, range, node or None, which)
    )
    return {**data, "geoip": request.app.state.logs.geo.ready}


def _any_store(request: Request, db):
    """Externer Speicher, wenn eingeschaltet – sonst SQLite über dieselbe Schnittstelle."""
    from tesseract.sqlstore import SqlStore

    return _store(request, db) or SqlStore(db)


def _own_domains(db, actor) -> set[str] | None:
    """Rolle „Eigene Dienste“: Domains der freigegebenen Hosts (sonst None = alle)."""
    from tesseract.db.models import Host
    from tesseract.uiaccess import visible_host_ids

    visible = visible_host_ids(db, actor)
    if visible is None:
        return None
    return {h.domain for h in db.query(Host).filter(Host.id.in_(visible))} if visible else set()


def _only_domains(data: dict[str, Any], domains: set[str]) -> dict[str, Any]:
    """Aktivität nur für diese Domains (Schlüssel = Domain)."""
    return {
        k: ({d: v for d, v in val.items() if d in domains} if isinstance(val, dict) else val)
        for k, val in data.items()
    }


@router.get("/host")
def host(
    request: Request, db: DB, actor: CurrentActor, domain: str, range: Range = "24h"
) -> dict[str, Any]:
    """Statistik eines Hosts: Kennzahlen mit Vorzeitraum, Verlauf, Herkunft, Pfade, Abgelehnte."""
    from tesseract import hoststats

    allowed = _own_domains(db, actor)
    if allowed is not None and domain.lower() not in allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Host nicht gefunden")

    store = _any_store(request, db)
    try:
        data = hoststats.host(store, domain.lower(), range)
    except StoreError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    return {**data, "source": store.kind}


@router.get("/activity")
def activity(request: Request, db: DB, actor: CurrentActor) -> dict[str, Any]:
    """Anfragen der letzten 24 Stunden je Host, stündlich – für die Hostliste."""
    from tesseract import hoststats

    store = _any_store(request, db)
    allowed = _own_domains(db, actor)
    try:
        data = hoststats.activity(store)
        if allowed is not None:
            data = _only_domains(data, allowed)
        return {**data, "source": store.kind}
    except StoreError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
