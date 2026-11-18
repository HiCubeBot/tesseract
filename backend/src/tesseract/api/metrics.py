"""Prometheus-Endpunkt `/metrics` und seine Einstellungen (Phase 5)."""

import hashlib
import ipaddress
import json
import secrets
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field

from tesseract import audit
from tesseract.api.iplists import normalize_networks
from tesseract.caddy.client import CaddyClient, CaddyError
from tesseract.db.models import Node, utcnow
from tesseract.deps import DB, AppSettings, CurrentActor, admin_device_for
from tesseract.metrics import CATALOG, caddy_only, render
from tesseract.services import get_general, resolve_ranges, set_general

public = APIRouter(tags=["metrics"])
router = APIRouter(prefix="/settings", tags=["settings"])


def _sha(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()


def _client_ip(request: Request) -> str:
    """Hinter Caddy steht die echte Client-IP in X-Forwarded-For (Caddy überschreibt den
    Header von Clients, die keine vertrauenswürdigen Proxys sind)."""
    fwd = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return fwd or (request.client.host if request.client else "")


def _allowed(request: Request, db, g: dict[str, Any]) -> bool:
    mode = g["metrics_auth"]
    if mode == "token":
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        return bool(token and g["metrics_token_hash"]) and secrets.compare_digest(
            _sha(token), g["metrics_token_hash"]
        )
    if mode == "mtls":
        return admin_device_for(request, db) is not None
    if mode == "ip":
        try:
            addr = ipaddress.ip_address(_client_ip(request))
        except ValueError:
            return False
        for net in resolve_ranges(db, g["metrics_networks"], g["metrics_list_ids"]):
            try:
                if addr in ipaddress.ip_network(net, strict=False):
                    return True
            except ValueError:
                continue
    return False


def _local_caddy(db, request: Request) -> dict[str, str]:
    out = {}
    for node in db.query(Node).filter(Node.kind == "local"):
        try:
            client = CaddyClient(node.admin_url, transport=request.app.state.caddy_transport)
            out[node.name] = caddy_only(client.metrics())
        except CaddyError:
            continue
    return out


@public.get("/metrics", include_in_schema=False)
def metrics(request: Request, db: DB, settings: AppSettings) -> Response:
    g = get_general(db)
    if not g["metrics_enabled"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Metriken sind ausgeschaltet")
    if not _allowed(request, db, g):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Kein Zugriff auf die Metriken")
    request.app.state.metrics_scraped_at = utcnow()
    caddy = _local_caddy(db, request) if g["metrics_caddy"] else {}
    if not g["metrics_caddy"]:
        request.app.state.logs.metrics.caddy.clear()
    text = render(db, settings, request.app.state.logs.metrics, caddy)
    return PlainTextResponse(text, media_type="text/plain; version=0.0.4; charset=utf-8")


# ---------- Einstellungen ----------


class ObservabilityOut(BaseModel):
    logs_days: int
    logs_ready: bool
    geoip: bool
    metrics_enabled: bool
    metrics_auth: str
    metrics_token_set: bool
    metrics_networks: list[str]
    metrics_list_ids: list[int]
    metrics_caddy: bool
    metrics_url: str
    last_scrape: datetime | None
    catalog: list[dict[str, str]]


class ObservabilityIn(BaseModel):
    logs_days: int = Field(14, ge=1, le=365)
    metrics_enabled: bool = False
    metrics_auth: Literal["token", "mtls", "ip"] = "token"
    metrics_networks: list[str] = Field(default_factory=list, max_length=200)
    metrics_list_ids: list[int] = Field(default_factory=list, max_length=20)
    metrics_caddy: bool = True


def _url(request: Request, settings) -> str:
    if settings.controller_domain:
        return f"https://{settings.controller_domain}/metrics"
    return str(request.base_url).rstrip("/") + "/metrics"


def _out(request: Request, db, settings) -> ObservabilityOut:
    g = get_general(db)
    return ObservabilityOut(
        logs_days=g["logs_days"],
        logs_ready=bool(settings.caddy_access_log and settings.access_log_path),
        geoip=request.app.state.logs.geo.ready,
        metrics_enabled=g["metrics_enabled"],
        metrics_auth=g["metrics_auth"],
        metrics_token_set=bool(g["metrics_token_hash"]),
        metrics_networks=g["metrics_networks"],
        metrics_list_ids=g["metrics_list_ids"],
        metrics_caddy=g["metrics_caddy"],
        metrics_url=_url(request, settings),
        last_scrape=getattr(request.app.state, "metrics_scraped_at", None),
        catalog=[{"name": n, "type": t, "help": h} for n, t, h in CATALOG],
    )


@router.get("/observability")
def get_observability(
    request: Request, db: DB, _: CurrentActor, settings: AppSettings
) -> ObservabilityOut:
    return _out(request, db, settings)


@router.put("/observability")
def put_observability(
    body: ObservabilityIn, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> ObservabilityOut:
    value = body.model_dump(exclude_unset=True)
    if "metrics_networks" in value:
        try:
            value["metrics_networks"] = normalize_networks(value["metrics_networks"])
        except ValueError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    before = get_general(db)
    after = {**before, **value}
    if (
        after["metrics_enabled"]
        and after["metrics_auth"] == "ip"
        and not (after["metrics_networks"] or after["metrics_list_ids"])
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Für „Nur IP-Liste“ mindestens ein Netz angeben"
        )
    set_general(db, value)
    changes = {k: [before.get(k), v] for k, v in value.items() if before.get(k) != v}
    if changes:
        audit.record(
            db,
            actor=actor.name,
            action="settings_changed",
            target="Logs & Metriken",
            details=changes,
            ip=actor.ip,
        )
    db.commit()
    return _out(request, db, settings)


@router.post("/observability/token")
def new_metrics_token(db: DB, actor: CurrentActor) -> dict[str, str]:
    """Neues Bearer-Token für Prometheus – wird nur jetzt einmal angezeigt."""
    token = "tsm_" + secrets.token_urlsafe(32)
    set_general(db, {"metrics_token_hash": _sha(token)})
    audit.record(
        db, actor=actor.name, action="settings_changed", target="Metriken-Token", ip=actor.ip
    )
    db.commit()
    return {"token": token}


@router.get("/observability/grafana.json")
def grafana_dashboard(_: CurrentActor) -> Response:
    """Fertiges Grafana-Dashboard für die Tesseract-Metriken."""
    from tesseract.grafana import dashboard

    return Response(
        json.dumps(dashboard(), indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="tesseract-grafana.json"'},
    )
