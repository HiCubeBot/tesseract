"""FastAPI-Abhängigkeiten: DB-Session, angemeldeter Admin."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from tesseract.auth import SESSION_COOKIE, session_for_token
from tesseract.config import Settings
from tesseract.db import Database
from tesseract.db.models import Admin
from tesseract.secretbox import SecretBox


def get_db(request: Request) -> Iterator[Session]:
    database: Database = request.app.state.db
    yield from database.session()


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_secretbox(request: Request) -> SecretBox:
    return request.app.state.secretbox


DB = Annotated[Session, Depends(get_db)]
Box = Annotated[SecretBox, Depends(get_secretbox)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]


@dataclass
class Actor:
    admin: Admin
    ip: str | None

    @property
    def name(self) -> str:
        return self.admin.username


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def current_actor(request: Request, db: DB) -> Actor:
    token = request.cookies.get(SESSION_COOKIE)
    session = session_for_token(db, token) if token else None
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nicht angemeldet")
    return Actor(admin=session.admin, ip=client_ip(request))


CurrentActor = Annotated[Actor, Depends(current_actor)]
