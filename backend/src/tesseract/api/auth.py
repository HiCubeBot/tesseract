from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from tesseract import audit
from tesseract.auth import (
    MIN_PASSWORD_LENGTH,
    SESSION_COOKIE,
    authenticate,
    create_session,
    end_session,
    set_password,
    verify_password,
)
from tesseract.deps import DB, AppSettings, CurrentActor, client_ip

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)
    remember: bool = False


class Me(BaseModel):
    username: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=256)


@router.post("/login")
def login(
    body: LoginRequest, request: Request, response: Response, db: DB, settings: AppSettings
) -> Me:
    throttle = request.app.state.login_throttle
    ip = client_ip(request) or "?"
    if throttle.blocked(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Zu viele Versuche – bitte warten")

    admin = authenticate(db, body.username, body.password)
    if admin is None:
        throttle.fail(ip)
        audit.record(db, actor=body.username or "?", action="login_failed", ip=ip)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Benutzername oder Passwort falsch")

    throttle.reset(ip)
    lifetime = (
        timedelta(days=settings.session_remember_days)
        if body.remember
        else timedelta(hours=settings.session_hours)
    )
    token, _ = create_session(
        db, admin, lifetime=lifetime, ip=ip, user_agent=request.headers.get("user-agent")
    )
    audit.record(db, actor=admin.username, action="login", ip=ip)
    db.commit()

    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(lifetime.total_seconds()) if body.remember else None,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return Me(username=admin.username)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DB) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        end_session(db, token)
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me")
def me(actor: CurrentActor) -> Me:
    return Me(username=actor.name)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordChange, actor: CurrentActor, db: DB, response: Response) -> None:
    admin = db.merge(actor.admin)
    if not verify_password(admin.password_hash, body.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aktuelles Passwort ist falsch")
    set_password(db, admin, body.new_password)  # beendet alle Sessions
    audit.record(db, actor=actor.name, action="password_changed", ip=actor.ip)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
