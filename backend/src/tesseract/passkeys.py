"""Passkeys (WebAuthn) für die Admin-Anmeldung – zusätzlich oder statt Passwort.

Passkeys sind „auffindbar“ (resident keys): Bei der Anmeldung muss niemand einen Namen
eingeben, der Browser bietet die passenden Passkeys an. Nutzerprüfung (PIN, Fingerabdruck,
Gesicht) ist Pflicht. Gespeichert wird nur der öffentliche Schlüssel.

Relying Party ist die Controller-Domain (`TESSERACT_CONTROLLER_DOMAIN`). Passkeys gelten nur für
genau diese Domain – nach einem Umzug auf eine andere Domain müssen sie neu angelegt werden.
"""

import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from tesseract.db.models import Admin, AdminPasskey, utcnow

CHALLENGE_SECONDS = 300
RP_NAME = "Tesseract"


class PasskeyError(Exception):
    pass


@dataclass
class _Challenge:
    value: bytes
    admin_id: int | None
    created: float = field(default_factory=time.monotonic)


class Challenges:
    """Offene Challenges im Speicher (5 Minuten, einmal verwendbar)."""

    def __init__(self) -> None:
        self.items: dict[str, _Challenge] = {}

    def put(self, value: bytes, admin_id: int | None) -> str:
        cutoff = time.monotonic() - CHALLENGE_SECONDS
        for k in [k for k, v in self.items.items() if v.created < cutoff]:
            del self.items[k]
        key = secrets.token_urlsafe(16)
        self.items[key] = _Challenge(value, admin_id)
        return key

    def take(self, key: str) -> _Challenge:
        c = self.items.pop(key, None)
        if c is None or time.monotonic() - c.created > CHALLENGE_SECONDS:
            raise PasskeyError("Anfrage abgelaufen – bitte erneut versuchen")
        return c


def relying_party(settings, request_url: str) -> tuple[str, list[str]]:
    """RP-ID (Domain) und erlaubte Origins."""
    if settings.controller_domain:
        domain = settings.controller_domain
        return domain, [f"https://{domain}"]
    # Entwicklung ohne Controller-Domain: Host der Anfrage (z. B. localhost:5173 über Vite)
    parts = urlsplit(request_url)
    host = parts.hostname or "localhost"
    origin = f"{parts.scheme}://{parts.netloc}"
    return host, [origin]


def registration_options(
    db: Session, challenges: Challenges, admin: Admin, rp_id: str
) -> dict[str, Any]:
    opts = generate_registration_options(
        rp_id=rp_id,
        rp_name=RP_NAME,
        user_id=f"tesseract-admin-{admin.id}".encode(),
        user_name=admin.username,
        user_display_name=admin.username,
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(p.credential_id))
            for p in admin.passkeys
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    key = challenges.put(opts.challenge, admin.id)
    return {"id": key, "options": json.loads(options_to_json(opts))}


def register(
    db: Session,
    challenges: Challenges,
    admin: Admin,
    key: str,
    credential: dict[str, Any],
    name: str,
    rp_id: str,
    origins: list[str],
) -> AdminPasskey:
    c = challenges.take(key)
    if c.admin_id != admin.id:
        raise PasskeyError("Anfrage gehört zu einem anderen Konto")
    try:
        v = verify_registration_response(
            credential=credential,
            expected_challenge=c.value,
            expected_rp_id=rp_id,
            expected_origin=origins,
            require_user_verification=True,
        )
    except InvalidRegistrationResponse as e:
        raise PasskeyError(f"Passkey nicht angenommen: {e}") from e
    cred_id = bytes_to_base64url(v.credential_id)
    if db.scalar(select(AdminPasskey.id).where(AdminPasskey.credential_id == cred_id)):
        raise PasskeyError("Dieser Passkey ist schon eingetragen")
    pk = AdminPasskey(
        admin_id=admin.id,
        name=(name.strip() or "Passkey")[:64],
        credential_id=cred_id,
        public_key=v.credential_public_key,
        sign_count=v.sign_count,
        transports=[str(t) for t in (credential.get("response", {}).get("transports") or [])][:8],
    )
    db.add(pk)
    db.flush()
    return pk


def login_options(challenges: Challenges, rp_id: str) -> dict[str, Any]:
    opts = generate_authentication_options(
        rp_id=rp_id, user_verification=UserVerificationRequirement.REQUIRED
    )
    key = challenges.put(opts.challenge, None)
    return {"id": key, "options": json.loads(options_to_json(opts))}


def login(
    db: Session,
    challenges: Challenges,
    key: str,
    credential: dict[str, Any],
    rp_id: str,
    origins: list[str],
) -> Admin:
    c = challenges.take(key)
    cred_id = str(credential.get("rawId") or credential.get("id") or "")
    pk = db.scalar(select(AdminPasskey).where(AdminPasskey.credential_id == cred_id))
    if pk is None:
        raise PasskeyError("Unbekannter Passkey")
    try:
        v = verify_authentication_response(
            credential=credential,
            expected_challenge=c.value,
            expected_rp_id=rp_id,
            expected_origin=origins,
            credential_public_key=pk.public_key,
            credential_current_sign_count=pk.sign_count,
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse as e:
        raise PasskeyError(f"Passkey-Anmeldung abgelehnt: {e}") from e
    pk.sign_count = v.new_sign_count
    pk.last_used_at = utcnow()
    pk.admin.last_login_at = utcnow()
    return pk.admin
