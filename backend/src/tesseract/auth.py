"""Admin-Anmeldung: Passwörter (argon2), Sessions, einfache Login-Bremse."""

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tesseract.db.models import Admin, AdminSession, utcnow

SESSION_COOKIE = "tesseract_session"
MIN_PASSWORD_LENGTH = 12

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def generate_password() -> str:
    return secrets.token_urlsafe(18)


def _token_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(db: Session, username: str, password: str) -> Admin | None:
    admin = db.scalar(select(Admin).where(Admin.username == username))
    if admin is None:
        # Gleiche Laufzeit wie bei falschem Passwort
        verify_password(_DUMMY_HASH, password)
        return None
    if not verify_password(admin.password_hash, password):
        return None
    if _hasher.check_needs_rehash(admin.password_hash):
        admin.password_hash = hash_password(password)
    return admin


def create_session(
    db: Session, admin: Admin, *, lifetime: timedelta, ip: str | None, user_agent: str | None
) -> tuple[str, AdminSession]:
    token = secrets.token_urlsafe(32)
    session = AdminSession(
        id=_token_id(token),
        admin_id=admin.id,
        expires_at=utcnow() + lifetime,
        ip=ip,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(session)
    return token, session


def session_for_token(db: Session, token: str) -> AdminSession | None:
    session = db.get(AdminSession, _token_id(token))
    if session is None or session.expires_at <= utcnow():
        return None
    return session


def end_session(db: Session, token: str) -> None:
    db.execute(delete(AdminSession).where(AdminSession.id == _token_id(token)))


def end_all_sessions(db: Session, admin_id: int) -> None:
    db.execute(delete(AdminSession).where(AdminSession.admin_id == admin_id))


def set_password(db: Session, admin: Admin, password: str) -> None:
    admin.password_hash = hash_password(password)
    admin.password_changed_at = utcnow()
    end_all_sessions(db, admin.id)


def ensure_admin(db: Session, username: str = "admin", password: str = "") -> str | None:
    """Erster Start: legt den Admin an. Ohne vorgegebenes Passwort mit einem Zufallspasswort,
    das zurückgegeben wird (fürs Log). Mit vorgegebenem Passwort (TESSERACT_ADMIN_PASSWORD)
    wird es bei jedem Start durchgesetzt – auch für einen bestehenden Admin."""
    if password:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"TESSERACT_ADMIN_PASSWORD ist zu kurz (mindestens {MIN_PASSWORD_LENGTH} Zeichen)"
            )
        admin = db.scalar(select(Admin).where(Admin.username == username))
        if admin is None:
            db.add(Admin(username=username, password_hash=hash_password(password)))
            db.commit()
        elif not verify_password(admin.password_hash, password):
            set_password(db, admin, password)  # beendet alle Sessions
            from tesseract import audit

            audit.record(
                db,
                actor="system",
                action="password_reset",
                target=username,
                details={"source": "TESSERACT_ADMIN_PASSWORD"},
            )
            db.commit()
        return None
    if db.scalar(select(Admin.id).limit(1)) is not None:
        return None
    password = generate_password()
    db.add(Admin(username=username, password_hash=hash_password(password)))
    db.commit()
    return password


class LoginThrottle:
    """Höchstens `limit` Fehlversuche pro IP in `window` Sekunden (im Speicher)."""

    def __init__(self, limit: int = 5, window: float = 300.0) -> None:
        self.limit = limit
        self.window = window
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        q = self._failures[key]
        cutoff = time.monotonic() - self.window
        while q and q[0] < cutoff:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        return len(self._prune(key)) >= self.limit

    def fail(self, key: str) -> None:
        self._prune(key).append(time.monotonic())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


_DUMMY_HASH = hash_password(secrets.token_hex(8))
