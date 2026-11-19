"""SSO für die Admin-Oberfläche per OpenID Connect (Authelia, Keycloak, Authentik, Dex …).

Ablauf: Authorization Code mit PKCE (S256), `state` und `nonce`. Das ID-Token wird über die
JWKS des Anbieters geprüft (Signatur, Aussteller, Empfänger, Ablauf, Nonce). Admin wird nur, wer
in der eingestellten Gruppe ist oder dessen E-Mail freigegeben ist. Das Admin-Gerätezertifikat
(mTLS) bleibt davor als erste Hürde bestehen.

Betrifft nur Admins der Oberfläche – nicht die Personen mit Zugriff auf Hosts.
"""

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.db.models import Admin, Setting, utcnow

SECRET_CONTEXT = "oidc-client-secret"
PENDING_SECONDS = 600
DISCOVERY_SECONDS = 3600

DEFAULTS: dict[str, Any] = {
    # Passwort-Anmeldung erlaubt (abschaltbar, wenn SSO oder Passkeys eingerichtet sind)
    "password_login": True,
    "oidc": {
        "enabled": False,
        "issuer": "",
        "client_id": "",
        "client_secret_enc": "",
        "scopes": "openid profile email groups",
        "label": "Mit SSO anmelden",
        # Wer Admin wird: Mitglied dieser Gruppe (Claim `groups_claim`) …
        "admin_group": "",
        "groups_claim": "groups",
        # … oder eine dieser (bestätigten) E-Mail-Adressen
        "allowed_emails": [],
        "username_claim": "preferred_username",
    },
}


class SSOError(Exception):
    pass


def get_config(db: Session) -> dict[str, Any]:
    row = db.get(Setting, "admin_auth")
    cfg = json.loads(json.dumps(DEFAULTS))
    for k, v in (row.value if row else {}).items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return cfg


def set_config(db: Session, value: dict[str, Any]) -> dict[str, Any]:
    cfg = {**get_config(db), **value}
    row = db.get(Setting, "admin_auth")
    if row is None:
        db.add(Setting(key="admin_auth", value=cfg))
    else:
        row.value = cfg
    return cfg


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@dataclass
class Pending:
    nonce: str
    verifier: str
    remember: bool
    created: float = field(default_factory=time.monotonic)


class OIDC:
    """Hält Discovery/JWKS im Zwischenspeicher und offene Anmeldungen (state) im Speicher."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport
        self.pending: dict[str, Pending] = {}
        self._discovery: dict[str, tuple[float, dict[str, Any]]] = {}

    def _http(self) -> httpx.Client:
        return httpx.Client(timeout=15.0, transport=self.transport, follow_redirects=True)

    def discovery(self, issuer: str) -> dict[str, Any]:
        issuer = issuer.rstrip("/")
        cached = self._discovery.get(issuer)
        if cached and time.monotonic() - cached[0] < DISCOVERY_SECONDS:
            return cached[1]
        try:
            with self._http() as c:
                r = c.get(f"{issuer}/.well-known/openid-configuration")
            r.raise_for_status()
            doc = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise SSOError(f"Anbieter nicht erreichbar oder keine OIDC-Discovery: {e}") from e
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri", "issuer"):
            if key not in doc:
                raise SSOError(f"Discovery unvollständig: {key} fehlt")
        if doc["issuer"].rstrip("/") != issuer:
            raise SSOError(f"Aussteller passt nicht: {doc['issuer']} statt {issuer}")
        self._discovery[issuer] = (time.monotonic(), doc)
        return doc

    def _prune(self) -> None:
        cutoff = time.monotonic() - PENDING_SECONDS
        for k in [k for k, v in self.pending.items() if v.created < cutoff]:
            del self.pending[k]

    def start(self, cfg: dict[str, Any], redirect_uri: str, remember: bool) -> str:
        """URL, zu der der Browser geschickt wird."""
        o = cfg["oidc"]
        doc = self.discovery(o["issuer"])
        self._prune()
        state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(48)
        challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
        self.pending[state] = Pending(nonce, verifier, remember)
        query = {
            "response_type": "code",
            "client_id": o["client_id"],
            "redirect_uri": redirect_uri,
            "scope": o["scopes"] or "openid",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        sep = "&" if "?" in doc["authorization_endpoint"] else "?"
        return doc["authorization_endpoint"] + sep + urlencode(query)

    def finish(
        self, cfg: dict[str, Any], secret: str, redirect_uri: str, state: str, code: str
    ) -> tuple[dict[str, Any], bool]:
        """Code einlösen und ID-Token prüfen. Gibt (Claims, „angemeldet bleiben“) zurück."""
        pending = self.pending.pop(state, None)
        if pending is None or time.monotonic() - pending.created > PENDING_SECONDS:
            raise SSOError("Anmeldung abgelaufen oder unbekannt – bitte neu starten")
        o = cfg["oidc"]
        doc = self.discovery(o["issuer"])
        try:
            with self._http() as c:
                r = c.post(
                    doc["token_endpoint"],
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "code_verifier": pending.verifier,
                    },
                    auth=(o["client_id"], secret),
                )
        except httpx.HTTPError as e:
            raise SSOError(f"Token-Endpunkt nicht erreichbar: {e}") from e
        if r.status_code != 200:
            raise SSOError(f"Anbieter lehnt den Code ab ({r.status_code}): {r.text[:200]}")
        tokens = r.json()
        claims = self._verify(doc, o["client_id"], tokens.get("id_token", ""), pending.nonce)
        # Gruppen stehen bei manchen Anbietern (z. B. Authelia) nur in Userinfo
        if o["groups_claim"] not in claims and doc.get("userinfo_endpoint"):
            try:
                with self._http() as c:
                    u = c.get(
                        doc["userinfo_endpoint"],
                        headers={"Authorization": f"Bearer {tokens.get('access_token', '')}"},
                    )
                if u.status_code == 200 and u.json().get("sub") == claims["sub"]:
                    claims = {**u.json(), **claims}
            except (httpx.HTTPError, ValueError):
                pass
        return claims, pending.remember

    def _verify(self, doc: dict[str, Any], client_id: str, token: str, nonce: str) -> dict:
        if not token:
            raise SSOError("Kein ID-Token erhalten")
        try:
            with self._http() as c:
                jwks = c.get(doc["jwks_uri"]).json()
            header = jwt.get_unverified_header(token)
            keys = [k for k in jwks.get("keys", []) if k.get("use", "sig") == "sig"]
            key = next((k for k in keys if k.get("kid") == header.get("kid")), None) or (
                keys[0] if len(keys) == 1 else None
            )
            if key is None:
                raise SSOError("Schlüssel des ID-Tokens nicht in den JWKS")
            claims = jwt.decode(
                token,
                jwt.PyJWK(key).key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "PS256", "EdDSA"],
                audience=client_id,
                issuer=doc["issuer"],
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
                leeway=60,
            )
        except jwt.PyJWTError as e:
            raise SSOError(f"ID-Token ungültig: {e}") from e
        except (httpx.HTTPError, ValueError) as e:
            raise SSOError(f"JWKS nicht lesbar: {e}") from e
        if claims.get("nonce") != nonce:
            raise SSOError("ID-Token passt nicht zu dieser Anmeldung (nonce)")
        return claims


def authorize(cfg: dict[str, Any], claims: dict[str, Any]) -> None:
    """Darf diese Person Admin sein?"""
    o = cfg["oidc"]
    groups = claims.get(o["groups_claim"]) or []
    if isinstance(groups, str):
        groups = [groups]
    if o["admin_group"] and o["admin_group"] in groups:
        return
    email = str(claims.get("email") or "").lower()
    allowed = [e.lower() for e in o["allowed_emails"]]
    if email and email in allowed and claims.get("email_verified", True) is not False:
        return
    raise SSOError("Kein Zugang: weder in der Admin-Gruppe noch freigegebene E-Mail")


def admin_for(db: Session, cfg: dict[str, Any], claims: dict[str, Any]) -> Admin:
    """Admin-Konto zu dieser Identität – beim ersten Mal angelegt (ohne Passwort)."""
    subject = f"{claims['iss']}|{claims['sub']}"
    admin = db.scalar(select(Admin).where(Admin.oidc_subject == subject))
    wanted = str(claims.get(cfg["oidc"]["username_claim"]) or claims.get("email") or claims["sub"])[
        :56
    ]
    if admin is None:
        name = wanted
        if db.scalar(select(Admin.id).where(Admin.username == name)):
            name = f"sso:{wanted}"[:64]
        n = 2
        while db.scalar(select(Admin.id).where(Admin.username == name)):
            name = f"sso:{wanted}-{n}"[:64]
            n += 1
        admin = Admin(
            username=name,
            # kein Passwort – Anmeldung nur über SSO (oder später einen Passkey)
            password_hash="!sso",
            source="oidc",
            oidc_subject=subject,
        )
        db.add(admin)
    admin.email = str(claims.get("email") or "")[:255] or admin.email
    admin.last_login_at = utcnow()
    db.flush()
    return admin
