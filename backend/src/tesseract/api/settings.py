import ipaddress
import re
import time
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select

from tesseract import __version__, audit
from tesseract.api.iplists import normalize_networks
from tesseract.db.models import Host, IpList, Node
from tesseract.deps import DB, AppSettings, CurrentActor, admin_device_for
from tesseract.services import admin_devices, apply_all, apply_node, get_general, set_general

router = APIRouter(prefix="/settings", tags=["settings"])


class GeneralIn(BaseModel):
    acme_email: EmailStr | None = None
    public_ips: list[str] = Field(default_factory=list, max_length=16)
    waf_default_mode: Literal["off", "detect", "block"] = "detect"
    waf_default_paranoia: int = Field(1, ge=1, le=4)
    controller_waf_mode: Literal["off", "detect", "block"] = "off"
    trusted_proxies: list[str] = Field(default_factory=list, max_length=200)
    trusted_proxy_list_ids: list[int] = Field(default_factory=list, max_length=20)
    authelia_url: str = Field("", max_length=255)
    authelia_headers: list[str] = Field(
        default_factory=lambda: ["Remote-User", "Remote-Groups", "Remote-Email", "Remote-Name"],
        max_length=20,
    )

    @field_validator("authelia_url")
    @classmethod
    def _authelia_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not v:
            return ""
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.path:
            raise ValueError("Adresse wie http://authelia:9091 oder https://auth.example.org")
        return v

    @field_validator("authelia_headers")
    @classmethod
    def _headers(cls, v: list[str]) -> list[str]:
        out = []
        for h in v:
            h = h.strip()
            if h and not re.fullmatch(r"[A-Za-z0-9-]{1,64}", h):
                raise ValueError(f"Ungültiger Header-Name: {h}")
            if h:
                out.append(h)
        return list(dict.fromkeys(out))

    @field_validator("trusted_proxies")
    @classmethod
    def _proxies(cls, v: list[str]) -> list[str]:
        return normalize_networks(v)

    @field_validator("public_ips")
    @classmethod
    def _ips(cls, v: list[str]) -> list[str]:
        return [str(ipaddress.ip_address(ip.strip())) for ip in v if ip.strip()]


class AdminAccessIn(BaseModel):
    enabled: bool


class AdminAccessOut(BaseModel):
    enabled: bool
    admin_devices: int
    # Gerät, mit dem diese Anfrage kommt (falls Admin-Gerät)
    current_device: str | None
    can_enable: bool
    reason: str | None
    apply_error: str | None = None


class GeneralOut(BaseModel):
    acme_email: str
    public_ips: list[str]
    waf_default_mode: str
    waf_default_paranoia: int
    controller_waf_mode: str
    trusted_proxies: list[str]
    trusted_proxy_list_ids: list[int]
    authelia_url: str
    authelia_headers: list[str]
    # nur lesbar – kommen aus der Umgebung
    controller_domain: str
    version: str


@router.get("/general")
def get_settings_general(db: DB, _: CurrentActor, settings: AppSettings) -> GeneralOut:
    g = get_general(db)
    return GeneralOut(
        acme_email=g["acme_email"],
        public_ips=g["public_ips"],
        waf_default_mode=g["waf_default_mode"],
        waf_default_paranoia=g["waf_default_paranoia"],
        controller_waf_mode=g["controller_waf_mode"],
        trusted_proxies=g["trusted_proxies"],
        trusted_proxy_list_ids=g["trusted_proxy_list_ids"],
        authelia_url=g["authelia_url"],
        authelia_headers=g["authelia_headers"],
        controller_domain=settings.controller_domain,
        version=__version__,
    )


@router.put("/general")
def put_settings_general(
    body: GeneralIn, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> GeneralOut:
    before = get_general(db)
    value = {
        "acme_email": body.acme_email or "",
        "public_ips": body.public_ips,
        "waf_default_mode": body.waf_default_mode,
        "waf_default_paranoia": body.waf_default_paranoia,
        "controller_waf_mode": body.controller_waf_mode,
        "trusted_proxies": body.trusted_proxies,
        "trusted_proxy_list_ids": body.trusted_proxy_list_ids,
        "authelia_url": body.authelia_url,
        "authelia_headers": body.authelia_headers,
    }
    if not body.authelia_url and db.scalar(select(Host.id).where(Host.authelia).limit(1)):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Authelia wird noch von Hosts genutzt – dort erst abschalten",
        )
    for i in body.trusted_proxy_list_ids:
        if db.get(IpList, i) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"IP-Liste {i} unbekannt")
    set_general(db, value)
    audit.record(
        db,
        actor=actor.name,
        action="settings_changed",
        target="general",
        details={"before": before, "after": value},
        ip=actor.ip,
    )
    db.commit()
    relevant = (
        "acme_email",
        "controller_waf_mode",
        "trusted_proxies",
        "trusted_proxy_list_ids",
        "authelia_url",
        "authelia_headers",
    )
    if any(before.get(k) != value[k] for k in relevant):
        for node in db.scalars(select(Node)):
            apply_node(db, node, settings, request.app.state.caddy_transport)
        db.commit()
    return get_settings_general(db, actor, settings)


def _admin_access(request: Request, db, settings) -> AdminAccessOut:
    g = get_general(db)
    current = admin_device_for(request, db)
    reason = None
    if not settings.controller_domain:
        reason = "Keine Controller-Domain gesetzt (TESSERACT_CONTROLLER_DOMAIN)"
    elif not admin_devices(db):
        reason = "Noch kein Gerät in der Gruppe „Admin“"
    elif current is None:
        reason = "Öffne die Oberfläche zuerst mit deinem Admin-Zertifikat"
    return AdminAccessOut(
        enabled=bool(g["admin_mtls"]),
        admin_devices=len(admin_devices(db)),
        current_device=f"{current.person.name} · {current.name}" if current else None,
        can_enable=reason is None,
        reason=reason,
    )


@router.get("/admin-access")
def get_admin_access(
    request: Request, db: DB, _: CurrentActor, settings: AppSettings
) -> AdminAccessOut:
    return _admin_access(request, db, settings)


@router.put("/admin-access")
def put_admin_access(
    body: AdminAccessIn, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> AdminAccessOut:
    state = _admin_access(request, db, settings)
    if body.enabled and not state.enabled and not state.can_enable:
        # Schutz vor dem Aussperren: nur mit einem gerade erkannten Admin-Gerät einschalten
        from fastapi import HTTPException, status

        raise HTTPException(status.HTTP_409_CONFLICT, state.reason or "Nicht möglich")
    if body.enabled != state.enabled:
        set_general(db, {"admin_mtls": body.enabled})
        audit.record(
            db,
            actor=actor.name,
            action="admin_mtls_on" if body.enabled else "admin_mtls_off",
            target="Oberfläche",
            details={"device": state.current_device},
            ip=actor.ip,
        )
        db.commit()
        errors = apply_all(db, settings, request.app.state.caddy_transport)
        db.commit()
        out = _admin_access(request, db, settings)
        out.apply_error = "; ".join(errors) or None
        return out
    return state


class AutheliaTest(BaseModel):
    ok: bool
    detail: str


@router.post("/authelia/test")
def test_authelia(db: DB, _: CurrentActor) -> AutheliaTest:
    """Prüft vom Controller aus, ob Authelia antwortet (GET /api/health)."""
    url = get_general(db)["authelia_url"]
    if not url:
        return AutheliaTest(ok=False, detail="Keine Adresse eingetragen")
    start = time.perf_counter()
    try:
        r = httpx.get(f"{url}/api/health", timeout=5.0)
    except httpx.HTTPError as e:
        return AutheliaTest(ok=False, detail=f"nicht erreichbar: {e}")
    ms = (time.perf_counter() - start) * 1000
    if r.status_code != 200:
        return AutheliaTest(ok=False, detail=f"antwortet mit {r.status_code}")
    return AutheliaTest(ok=True, detail=f"erreichbar · {ms:.0f} ms")
