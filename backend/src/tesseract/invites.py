"""Einladungen: Link + separat übermittelter Bestätigungscode + Freigabe durch den Admin."""

import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.db.models import Enrollment, Invite, Person, utcnow
from tesseract.secretbox import SecretBox

TOKEN_CONTEXT = "invite-token"
CODE_CONTEXT = "invite-code"
MAX_FAILED_CODES = 5
DEFAULT_DAYS = 7


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(18)


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def format_code(code: str) -> str:
    return f"{code[:3]} {code[3:]}"


def create_invite(
    db: Session, box: SecretBox, person: Person, *, actor: str, days: int = DEFAULT_DAYS
) -> tuple[Invite, str, str]:
    token, code = new_token(), new_code()
    invite = Invite(
        person_id=person.id,
        token_hash=sha256(token),
        token_enc=box.encrypt(token.encode(), TOKEN_CONTEXT),
        code_enc=box.encrypt(code.encode(), CODE_CONTEXT),
        created_by=actor,
        expires_at=utcnow() + timedelta(days=days),
    )
    db.add(invite)
    return invite, token, code


def invite_token(box: SecretBox, invite: Invite) -> str:
    return box.decrypt(invite.token_enc, TOKEN_CONTEXT).decode()


def invite_code(box: SecretBox, invite: Invite) -> str:
    return box.decrypt(invite.code_enc, CODE_CONTEXT).decode()


def invite_state(invite: Invite) -> str:
    if invite.revoked_at is not None:
        return "revoked"
    if invite.expires_at <= utcnow():
        return "expired"
    return "open"


def find_invite(db: Session, token: str) -> Invite | None:
    return db.scalar(select(Invite).where(Invite.token_hash == sha256(token)))


def check_code(box: SecretBox, invite: Invite, code: str) -> bool:
    given = "".join(ch for ch in code if ch.isdigit())
    return hmac.compare_digest(given, invite_code(box, invite))


def find_enrollment(invite: Invite, enrollment_id: int, secret: str) -> Enrollment | None:
    for e in invite.enrollments:
        if e.id == enrollment_id and hmac.compare_digest(e.secret_hash, sha256(secret)):
            return e
    return None


def open_requests(invite: Invite) -> int:
    return sum(1 for e in invite.enrollments if e.status in ("pending", "approved"))
