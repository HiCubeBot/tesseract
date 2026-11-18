"""Benannte IP-Listen (für IP-Filter und vertrauenswürdige Proxys)."""

import ipaddress
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from tesseract import audit
from tesseract.db.models import Host, IpList
from tesseract.deps import DB, AppSettings, CurrentActor
from tesseract.services import apply_all, get_general

router = APIRouter(prefix="/ip-lists", tags=["ip-lists"])

MAX_ENTRIES = 2000


def normalize_network(value: str) -> str:
    """`1.2.3.4` → `1.2.3.4/32`, `10.0.0.5/24` → `10.0.0.0/24`."""
    try:
        return str(ipaddress.ip_network(value.strip(), strict=False))
    except ValueError as e:
        raise ValueError(f"Keine gültige IP bzw. kein Netz: {value.strip()}") from e


def normalize_networks(values: list[str]) -> list[str]:
    return list(dict.fromkeys(normalize_network(v) for v in values if v.strip()))


class IpListIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str = Field("", max_length=255)
    entries: list[str] = Field(default_factory=list, max_length=MAX_ENTRIES)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Name darf nicht leer sein")
        return v

    @field_validator("entries")
    @classmethod
    def _entries(cls, v: list[str]) -> list[str]:
        return normalize_networks(v)


class IpListOut(BaseModel):
    id: int
    name: str
    description: str
    entries: list[str]
    used_by: list[str]
    updated_at: datetime


def _used_by(db, lst: IpList) -> list[str]:
    used = [
        h.domain
        for h in db.scalars(select(Host).order_by(Host.domain))
        if lst.id in (h.ip_list_ids or [])
    ]
    g = get_general(db)
    if lst.id in g["trusted_proxy_list_ids"]:
        used.append("Vertrauenswürdige Proxys")
    if lst.id in g["internal_list_ids"]:
        used.append("Interne Netze")
    return used


def _out(db, lst: IpList) -> IpListOut:
    return IpListOut(
        id=lst.id,
        name=lst.name,
        description=lst.description,
        entries=lst.entries,
        used_by=_used_by(db, lst),
        updated_at=lst.updated_at,
    )


def _get(db, list_id: int) -> IpList:
    lst = db.get(IpList, list_id)
    if lst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Liste nicht gefunden")
    return lst


def _commit(db) -> None:
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Eine Liste mit diesem Namen gibt es schon"
        ) from e


@router.get("")
def list_lists(db: DB, _: CurrentActor) -> list[IpListOut]:
    return [_out(db, lst) for lst in db.scalars(select(IpList).order_by(IpList.name))]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_list(body: IpListIn, db: DB, actor: CurrentActor) -> IpListOut:
    lst = IpList(name=body.name, description=body.description, entries=body.entries)
    db.add(lst)
    audit.record(
        db,
        actor=actor.name,
        action="iplist_created",
        target=body.name,
        details={"entries": len(body.entries)},
        ip=actor.ip,
    )
    _commit(db)
    return _out(db, lst)


@router.put("/{list_id}")
def update_list(
    list_id: int,
    body: IpListIn,
    request: Request,
    db: DB,
    actor: CurrentActor,
    settings: AppSettings,
) -> IpListOut:
    lst = _get(db, list_id)
    changed = lst.entries != body.entries
    before = len(lst.entries)
    lst.name, lst.description, lst.entries = body.name, body.description, body.entries
    audit.record(
        db,
        actor=actor.name,
        action="iplist_updated",
        target=body.name,
        details={"before": before, "after": len(body.entries)},
        ip=actor.ip,
    )
    _commit(db)
    if changed and _used_by(db, lst):
        apply_all(db, settings, request.app.state.caddy_transport)
        db.commit()
    return _out(db, lst)


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_list(list_id: int, db: DB, actor: CurrentActor) -> None:
    lst = _get(db, list_id)
    used = _used_by(db, lst)
    if used:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Die Liste wird noch verwendet: {', '.join(used)}"
        )
    audit.record(db, actor=actor.name, action="iplist_deleted", target=lst.name, ip=actor.ip)
    db.delete(lst)
    db.commit()
