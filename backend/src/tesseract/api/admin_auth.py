"""Admin-Anmeldung per SSO (OIDC) und Passkey sowie deren Einstellungen."""

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from tesseract import audit, passkeys, sso
from tesseract.api.auth import Me, start_session
from tesseract.db.models import AdminPasskey
from tesseract.deps import DB, AppSettings, Box, CurrentActor, client_ip, require_admin_device

router = APIRouter(prefix="/auth", tags=["auth"])
settings_router = APIRouter(prefix="/settings", tags=["settings"])


def _redirect_uri(request: Request, settings) -> str:
    from tesseract.api.install import controller_url

    return controller_url(request, settings) + "/api/auth/sso/callback"


# ---------- SSO ----------


@router.get("/sso/start", include_in_schema=False)
def sso_start(request: Request, db: DB, settings: AppSettings, remember: bool = False):
    require_admin_device(request, db)
    cfg = sso.get_config(db)
    if not cfg["oidc"]["enabled"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SSO ist nicht eingerichtet")
    try:
        url = request.app.state.oidc.start(cfg, _redirect_uri(request, settings), remember)
    except sso.SSOError as e:
        return RedirectResponse(f"/#/login?fehler={quote(str(e))}", status_code=303)
    return RedirectResponse(url, status_code=303)


@router.get("/sso/callback", include_in_schema=False)
def sso_callback(
    request: Request,
    db: DB,
    box: Box,
    settings: AppSettings,
    state: str = "",
    code: str = "",
    error: str = "",
    error_description: str = "",
):
    """Rückkehr vom Anbieter: Code einlösen, prüfen, Admin anmelden, zur Oberfläche."""
    require_admin_device(request, db)
    ip = client_ip(request)

    def fail(msg: str) -> RedirectResponse:
        audit.record(db, actor="SSO", action="login_failed", details={"error": msg[:200]}, ip=ip)
        db.commit()
        return RedirectResponse(f"/#/login?fehler={quote(msg)}", status_code=303)

    if error:
        return fail(f"Anbieter meldet: {error_description or error}")
    cfg = sso.get_config(db)
    if not cfg["oidc"]["enabled"]:
        return fail("SSO ist nicht eingerichtet")
    secret = (
        box.decrypt(cfg["oidc"]["client_secret_enc"], sso.SECRET_CONTEXT).decode()
        if (cfg["oidc"]["client_secret_enc"])
        else ""
    )
    try:
        claims, remember = request.app.state.oidc.finish(
            cfg, secret, _redirect_uri(request, settings), state, code
        )
        sso.authorize(cfg, claims)
    except sso.SSOError as e:
        return fail(str(e))
    admin = sso.admin_for(db, cfg, claims)
    response = RedirectResponse("/#/", status_code=303)
    start_session(request, response, db, settings, admin, remember, "sso")
    return response


# ---------- Passkeys: Anmeldung ----------


class PasskeyLogin(BaseModel):
    id: str = Field(max_length=64)
    credential: dict[str, Any]
    remember: bool = False


@router.post("/passkey/options")
def passkey_login_options(request: Request, db: DB, settings: AppSettings) -> dict[str, Any]:
    require_admin_device(request, db)
    rp_id, _ = passkeys.relying_party(settings, _origin_url(request))
    return passkeys.login_options(request.app.state.passkey_challenges, rp_id)


def _origin_url(request: Request) -> str:
    # Hinter Vite/Caddy zählt, was der Browser als Origin sieht
    return request.headers.get("origin") or str(request.base_url)


@router.post("/passkey/login")
def passkey_login(
    body: PasskeyLogin, request: Request, response: Response, db: DB, settings: AppSettings
) -> Me:
    require_admin_device(request, db)
    throttle = request.app.state.login_throttle
    ip = client_ip(request) or "?"
    if throttle.blocked(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Zu viele Versuche – bitte warten")
    rp_id, origins = passkeys.relying_party(settings, _origin_url(request))
    try:
        admin = passkeys.login(
            db, request.app.state.passkey_challenges, body.id, body.credential, rp_id, origins
        )
    except passkeys.PasskeyError as e:
        throttle.fail(ip)
        audit.record(
            db, actor="Passkey", action="login_failed", details={"error": str(e)[:200]}, ip=ip
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    throttle.reset(ip)
    return start_session(request, response, db, settings, admin, body.remember, "passkey")


# ---------- Passkeys: verwalten (angemeldet) ----------


class PasskeyOut(BaseModel):
    id: int
    name: str
    created_at: Any
    last_used_at: Any


class PasskeyRegister(BaseModel):
    id: str = Field(max_length=64)
    credential: dict[str, Any]
    name: str = Field("Passkey", max_length=64)


@router.get("/passkeys")
def list_passkeys(db: DB, actor: CurrentActor) -> list[PasskeyOut]:
    admin = db.merge(actor.account)
    return [
        PasskeyOut(id=p.id, name=p.name, created_at=p.created_at, last_used_at=p.last_used_at)
        for p in admin.passkeys
    ]


@router.post("/passkeys/options")
def passkey_register_options(
    request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> dict[str, Any]:
    rp_id, _ = passkeys.relying_party(settings, _origin_url(request))
    return passkeys.registration_options(
        db, request.app.state.passkey_challenges, db.merge(actor.account), rp_id
    )


@router.post("/passkeys", status_code=status.HTTP_201_CREATED)
def passkey_register(
    body: PasskeyRegister, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> PasskeyOut:
    rp_id, origins = passkeys.relying_party(settings, _origin_url(request))
    admin = db.merge(actor.account)
    try:
        pk = passkeys.register(
            db,
            request.app.state.passkey_challenges,
            admin,
            body.id,
            body.credential,
            body.name,
            rp_id,
            origins,
        )
    except passkeys.PasskeyError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    audit.record(db, actor=actor.name, action="passkey_added", target=pk.name, ip=actor.ip)
    db.commit()
    return PasskeyOut(id=pk.id, name=pk.name, created_at=pk.created_at, last_used_at=None)


@router.delete("/passkeys/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT)
def passkey_delete(passkey_id: int, db: DB, actor: CurrentActor) -> None:
    pk = db.get(AdminPasskey, passkey_id)
    if pk is None or pk.admin_id != actor.account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Passkey nicht gefunden")
    cfg = sso.get_config(db)
    # Nicht aussperren: letzter Weg hinein?
    others = db.scalar(
        select(func.count()).select_from(AdminPasskey).where(AdminPasskey.id != pk.id)
    )
    if not cfg["password_login"] and not cfg["oidc"]["enabled"] and not others:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Letzter Anmeldeweg – erst Passwort-Anmeldung wieder einschalten oder SSO einrichten",
        )
    audit.record(db, actor=actor.name, action="passkey_removed", target=pk.name, ip=actor.ip)
    db.delete(pk)
    db.commit()


# ---------- Einstellungen ----------


class OIDCIn(BaseModel):
    enabled: bool = False
    issuer: str = Field("", max_length=500)
    client_id: str = Field("", max_length=255)
    # None = unverändert, "" = löschen
    client_secret: str | None = Field(None, max_length=500)
    scopes: str = Field("openid profile email groups", max_length=255)
    label: str = Field("Mit SSO anmelden", max_length=64)
    admin_group: str = Field("", max_length=255)
    groups_claim: str = Field("groups", max_length=64)
    allowed_emails: list[str] = Field(default_factory=list, max_length=50)
    username_claim: str = Field("preferred_username", max_length=64)


class AdminAuthIn(BaseModel):
    password_login: bool | None = None
    oidc: OIDCIn | None = None


def _out(cfg: dict[str, Any], request: Request, db) -> dict[str, Any]:
    o = {k: v for k, v in cfg["oidc"].items() if k != "client_secret_enc"}
    o["client_secret_set"] = bool(cfg["oidc"]["client_secret_enc"])
    return {
        "password_login": cfg["password_login"],
        "oidc": o,
        "redirect_uri": _redirect_uri(request, request.app.state.settings),
        "passkeys_total": db.scalar(select(func.count()).select_from(AdminPasskey)) or 0,
    }


@settings_router.get("/admin-auth")
def get_admin_auth(request: Request, db: DB, _: CurrentActor) -> dict[str, Any]:
    return _out(sso.get_config(db), request, db)


@settings_router.put("/admin-auth")
def put_admin_auth(
    body: AdminAuthIn, request: Request, db: DB, box: Box, actor: CurrentActor
) -> dict[str, Any]:
    cfg = sso.get_config(db)
    value: dict[str, Any] = {}
    if body.oidc is not None:
        o = body.oidc
        enc = cfg["oidc"]["client_secret_enc"]
        if o.client_secret is not None:
            enc = (
                box.encrypt(o.client_secret.encode(), sso.SECRET_CONTEXT) if o.client_secret else ""
            )
        new = {**o.model_dump(exclude={"client_secret"}), "client_secret_enc": enc}
        new["issuer"] = new["issuer"].strip().rstrip("/")
        new["allowed_emails"] = [e.strip().lower() for e in new["allowed_emails"] if e.strip()]
        if new["enabled"]:
            if not new["issuer"].startswith("https://") and not new["issuer"].startswith(
                "http://localhost"
            ):
                raise HTTPException(422, "Aussteller (Issuer) muss mit https:// beginnen")
            if not new["client_id"]:
                raise HTTPException(422, "Client-ID fehlt")
            if not (new["admin_group"] or new["allowed_emails"]):
                raise HTTPException(
                    422, "Festlegen, wer Admin wird: Admin-Gruppe oder freigegebene E-Mails"
                )
            try:
                request.app.state.oidc.discovery(new["issuer"])
            except sso.SSOError as e:
                raise HTTPException(422, str(e)) from e
        value["oidc"] = new
    if body.password_login is not None:
        value["password_login"] = body.password_login
    merged = {**cfg, **value}
    if not merged["password_login"]:
        has_pk = db.scalar(select(func.count()).select_from(AdminPasskey))
        if not merged["oidc"]["enabled"] and not has_pk:
            raise HTTPException(
                409,
                "Passwort-Anmeldung lässt sich erst abschalten, wenn SSO oder ein Passkey "
                "eingerichtet ist",
            )
    cfg = sso.set_config(db, value)
    audit.record(
        db,
        actor=actor.name,
        action="settings_changed",
        target="Admin-Anmeldung",
        details={"changed": sorted(value)},
        ip=actor.ip,
    )
    db.commit()
    return _out(cfg, request, db)
