"""Gruppen, Personen und Geräte."""

import base64
import csv
import io
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tesseract import audit, pki
from tesseract.db.models import Device, Group, Person
from tesseract.deps import DB, AppSettings, Box, CurrentActor
from tesseract.identity import CAError, active_device_count, issue_device, revoke_device
from tesseract.services import apply_all

router = APIRouter(tags=["people"])


# ---------- Schemas ----------


def _clean_name(v: str) -> str:
    v = " ".join(v.split())
    if not v:
        raise ValueError("Name darf nicht leer sein")
    return v


class GroupIn(BaseModel):
    name: str = Field(max_length=64)
    description: str = Field("", max_length=255)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _clean_name(v)


class GroupOut(BaseModel):
    id: int
    name: str
    description: str
    builtin: bool
    members: int


class PersonIn(BaseModel):
    name: str = Field(max_length=64)
    note: str = Field("", max_length=255)
    max_devices: int = Field(3, ge=1, le=20)
    disabled: bool = False
    group_ids: list[int] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _clean_name(v)


class GroupRef(BaseModel):
    id: int
    name: str


class DeviceOut(BaseModel):
    id: int
    person_id: int
    person_name: str
    name: str
    platform: str
    serial: str
    fingerprint: str
    not_before: datetime
    not_after: datetime
    unlimited: bool
    status: Literal["active", "expired", "revoked"]
    revoked_at: datetime | None
    revoke_reason: str
    last_seen_at: datetime | None
    created_at: datetime


class PersonOut(BaseModel):
    id: int
    name: str
    note: str
    max_devices: int
    disabled: bool
    created_at: datetime
    groups: list[GroupRef]
    devices: list[DeviceOut]
    active_devices: int


class IssueIn(BaseModel):
    name: str = Field(max_length=64)
    platform: str = Field("", max_length=32)
    # None = so lange wie das Zwischenzertifikat („unbegrenzt“)
    days: int | None = Field(365, ge=1, le=3650)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _clean_name(v)


class IssueOut(BaseModel):
    device: DeviceOut
    filename: str
    password: str
    p12_base64: str


class RevokeIn(BaseModel):
    reason: str = Field("", max_length=255)


# ---------- Hilfen ----------


def device_out(d: Device) -> DeviceOut:
    return DeviceOut(
        id=d.id,
        person_id=d.person_id,
        person_name=d.person.name,
        name=d.name,
        platform=d.platform,
        serial=d.serial,
        fingerprint=pki.format_fingerprint(d.fingerprint),
        not_before=d.not_before,
        not_after=d.not_after,
        unlimited=d.unlimited,
        status=d.status,  # type: ignore[arg-type]
        revoked_at=d.revoked_at,
        revoke_reason=d.revoke_reason,
        last_seen_at=d.last_seen_at,
        created_at=d.created_at,
    )


def person_out(db: Session, p: Person) -> PersonOut:
    return PersonOut(
        id=p.id,
        name=p.name,
        note=p.note,
        max_devices=p.max_devices,
        disabled=p.disabled,
        created_at=p.created_at,
        groups=[GroupRef(id=g.id, name=g.name) for g in p.groups],
        devices=[device_out(d) for d in p.devices],
        active_devices=active_device_count(db, p.id),
    )


def _get(db: Session, model, obj_id: int, what: str):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{what} nicht gefunden")
    return obj


def _groups(db: Session, ids: list[int]) -> list[Group]:
    groups = list(db.scalars(select(Group).where(Group.id.in_(ids)))) if ids else []
    if len(groups) != len(set(ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unbekannte Gruppe")
    return groups


def _commit_unique(db: Session, what: str) -> None:
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"{what} gibt es schon") from e


def _reapply(request: Request, db: Session, settings) -> None:
    apply_all(db, settings, request.app.state.caddy_transport)
    db.commit()


# ---------- Gruppen ----------


@router.get("/groups")
def list_groups(db: DB, _: CurrentActor) -> list[GroupOut]:
    return [
        GroupOut(
            id=g.id,
            name=g.name,
            description=g.description,
            builtin=g.builtin,
            members=len(g.persons),
        )
        for g in db.scalars(select(Group).order_by(Group.builtin.desc(), Group.name))
    ]


@router.post("/groups", status_code=status.HTTP_201_CREATED)
def create_group(body: GroupIn, db: DB, actor: CurrentActor) -> GroupOut:
    g = Group(name=body.name, description=body.description)
    db.add(g)
    audit.record(db, actor=actor.name, action="group_created", target=body.name, ip=actor.ip)
    _commit_unique(db, "Diese Gruppe")
    return GroupOut(id=g.id, name=g.name, description=g.description, builtin=False, members=0)


@router.put("/groups/{group_id}")
def update_group(group_id: int, body: GroupIn, db: DB, actor: CurrentActor) -> GroupOut:
    g: Group = _get(db, Group, group_id, "Gruppe")
    if g.builtin and body.name != g.name:
        raise HTTPException(status.HTTP_409_CONFLICT, "Eingebaute Gruppen behalten ihren Namen")
    g.name, g.description = body.name, body.description
    audit.record(db, actor=actor.name, action="group_updated", target=g.name, ip=actor.ip)
    _commit_unique(db, "Diese Gruppe")
    return GroupOut(
        id=g.id, name=g.name, description=g.description, builtin=g.builtin, members=len(g.persons)
    )


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> None:
    g: Group = _get(db, Group, group_id, "Gruppe")
    if g.builtin:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Eingebaute Gruppen lassen sich nicht löschen"
        )
    audit.record(db, actor=actor.name, action="group_deleted", target=g.name, ip=actor.ip)
    db.delete(g)
    db.commit()
    _reapply(request, db, settings)


# ---------- Personen ----------


@router.get("/persons")
def list_persons(db: DB, _: CurrentActor) -> list[PersonOut]:
    return [person_out(db, p) for p in db.scalars(select(Person).order_by(Person.name))]


@router.post("/persons", status_code=status.HTTP_201_CREATED)
def create_person(body: PersonIn, db: DB, actor: CurrentActor) -> PersonOut:
    p = Person(name=body.name, note=body.note, max_devices=body.max_devices, disabled=body.disabled)
    p.groups = _groups(db, body.group_ids)
    db.add(p)
    audit.record(
        db,
        actor=actor.name,
        action="person_created",
        target=body.name,
        details={"groups": [g.name for g in p.groups]},
        ip=actor.ip,
    )
    _commit_unique(db, "Eine Person mit diesem Namen")
    return person_out(db, p)


@router.get("/persons/{person_id}")
def get_person(person_id: int, db: DB, _: CurrentActor) -> PersonOut:
    return person_out(db, _get(db, Person, person_id, "Person"))


@router.put("/persons/{person_id}")
def update_person(
    person_id: int,
    body: PersonIn,
    request: Request,
    db: DB,
    actor: CurrentActor,
    settings: AppSettings,
) -> PersonOut:
    p: Person = _get(db, Person, person_id, "Person")
    before = {"groups": sorted(g.name for g in p.groups), "disabled": p.disabled}
    p.name, p.note, p.max_devices, p.disabled = (
        body.name,
        body.note,
        body.max_devices,
        body.disabled,
    )
    p.groups = _groups(db, body.group_ids)
    after = {"groups": sorted(g.name for g in p.groups), "disabled": p.disabled}
    audit.record(
        db,
        actor=actor.name,
        action="person_updated",
        target=p.name,
        details={"before": before, "after": after} if before != after else {},
        ip=actor.ip,
    )
    _commit_unique(db, "Eine Person mit diesem Namen")
    if before != after:
        _reapply(request, db, settings)
    return person_out(db, p)


@router.delete("/persons/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(
    person_id: int, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> None:
    p: Person = _get(db, Person, person_id, "Person")
    audit.record(
        db,
        actor=actor.name,
        action="person_deleted",
        target=p.name,
        details={"devices": len(p.devices)},
        ip=actor.ip,
    )
    db.delete(p)
    db.commit()
    _reapply(request, db, settings)


# ---------- Geräte ----------


@router.get("/devices")
def list_devices(db: DB, _: CurrentActor) -> list[DeviceOut]:
    return [device_out(d) for d in db.scalars(select(Device).order_by(Device.created_at.desc()))]


@router.post("/persons/{person_id}/devices", status_code=status.HTTP_201_CREATED)
def issue(
    person_id: int,
    body: IssueIn,
    request: Request,
    db: DB,
    box: Box,
    actor: CurrentActor,
    settings: AppSettings,
) -> IssueOut:
    """Stellt direkt ein Zertifikat aus (z. B. für das eigene Admin-Gerät).
    Die .p12 wird genau einmal ausgeliefert; der Schlüssel wird nicht gespeichert."""
    p: Person = _get(db, Person, person_id, "Person")
    try:
        issued = issue_device(db, box, p, name=body.name, platform=body.platform, days=body.days)
    except CAError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    db.flush()
    audit.record(
        db,
        actor=actor.name,
        action="device_issued",
        target=f"{p.name} · {body.name}",
        details={"serial": issued.device.serial, "not_after": issued.device.not_after.isoformat()},
        ip=actor.ip,
    )
    db.commit()
    # Neues Gerät → Freigabelisten der Hosts ergänzen und neu übertragen
    _reapply(request, db, settings)
    return IssueOut(
        device=device_out(issued.device),
        filename=issued.filename,
        password=issued.password,
        p12_base64=base64.b64encode(issued.p12).decode(),
    )


@router.post("/devices/{device_id}/revoke")
def revoke(
    device_id: int,
    body: RevokeIn,
    request: Request,
    db: DB,
    actor: CurrentActor,
    settings: AppSettings,
) -> DeviceOut:
    d: Device = _get(db, Device, device_id, "Gerät")
    if d.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Das Gerät ist bereits gesperrt")
    revoke_device(d, body.reason)
    audit.record(
        db,
        actor=actor.name,
        action="device_revoked",
        target=f"{d.person.name} · {d.name}",
        details={"serial": d.serial, "reason": body.reason},
        ip=actor.ip,
    )
    db.commit()
    _reapply(request, db, settings)
    return device_out(d)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(device_id: int, db: DB, actor: CurrentActor) -> None:
    """Gerät endgültig entfernen – nur, wenn es gesperrt oder abgelaufen ist.
    Aktive Geräte erst sperren, damit ihr Zertifikat sicher nirgends mehr gilt."""
    d: Device = _get(db, Device, device_id, "Gerät")
    if d.status == "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "Aktive Geräte erst sperren, dann löschen")
    audit.record(
        db,
        actor=actor.name,
        action="device_deleted",
        target=f"{d.person.name} · {d.name}",
        details={"serial": d.serial, "fingerprint": d.fingerprint, "status": d.status},
        ip=actor.ip,
    )
    db.delete(d)
    db.commit()


@router.get("/devices/revoked.csv")
def revoked_csv(db: DB, _: CurrentActor) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(
        ["Person", "Gerät", "Seriennummer", "Fingerabdruck (SHA-256)", "Gesperrt am", "Grund"]
    )
    for d in db.scalars(
        select(Device).where(Device.revoked_at.is_not(None)).order_by(Device.revoked_at)
    ):
        w.writerow(
            [
                d.person.name,
                d.name,
                d.serial,
                pki.format_fingerprint(d.fingerprint),
                d.revoked_at.isoformat() if d.revoked_at else "",
                d.revoke_reason,
            ]
        )
    return Response(
        "﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="gesperrte-geraete.csv"'},
    )
