"""Zugriffsmatrix: Gruppen und Personen × geschützte Hosts."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from tesseract import audit
from tesseract.db.models import Group, Host, Person
from tesseract.deps import DB, AppSettings, CurrentActor
from tesseract.services import add_version, apply_all, diff, set_grants, snapshot

router = APIRouter(prefix="/access", tags=["access"])


class Cell(BaseModel):
    host_id: int
    kind: Literal["group", "person"]
    id: int


class MatrixHost(BaseModel):
    id: int
    domain: str
    access: str
    paths: list[str]


class MatrixGroup(BaseModel):
    id: int
    name: str
    members: list[int]


class MatrixPerson(BaseModel):
    id: int
    name: str
    disabled: bool
    group_ids: list[int]


class Matrix(BaseModel):
    hosts: list[MatrixHost]
    groups: list[MatrixGroup]
    persons: list[MatrixPerson]
    grants: list[Cell]


class MatrixIn(BaseModel):
    grants: list[Cell]


def _protected_hosts(db) -> list[Host]:
    hosts = db.scalars(select(Host).order_by(Host.domain)).all()
    return [h for h in hosts if h.access == "mtls" or h.paths]


@router.get("")
def get_matrix(db: DB, _: CurrentActor) -> Matrix:
    hosts = _protected_hosts(db)
    groups = db.scalars(select(Group).order_by(Group.builtin.desc(), Group.name)).all()
    persons = db.scalars(select(Person).order_by(Person.name)).all()
    cells = [
        Cell(
            host_id=h.id,
            kind="group" if g.group_id is not None else "person",
            id=g.group_id if g.group_id is not None else g.person_id,  # type: ignore[arg-type]
        )
        for h in hosts
        for g in h.grants
    ]
    return Matrix(
        hosts=[
            MatrixHost(id=h.id, domain=h.domain, access=h.access, paths=[p.path for p in h.paths])
            for h in hosts
        ],
        groups=[
            MatrixGroup(id=g.id, name=g.name, members=[p.id for p in g.persons]) for g in groups
        ],
        persons=[
            MatrixPerson(
                id=p.id, name=p.name, disabled=p.disabled, group_ids=[g.id for g in p.groups]
            )
            for p in persons
        ],
        grants=cells,
    )


@router.put("")
def put_matrix(
    body: MatrixIn, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> dict:
    """Ersetzt die Freigaben aller geschützten Hosts. Geänderte Hosts bekommen eine Version."""
    hosts = {h.id: h for h in _protected_hosts(db)}
    group_ids = set(db.scalars(select(Group.id)))
    person_ids = set(db.scalars(select(Person.id)))
    wanted: dict[int, tuple[list[int], list[int]]] = {hid: ([], []) for hid in hosts}
    for c in body.grants:
        if c.host_id not in hosts:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Host ist nicht geschützt")
        if (c.kind == "group" and c.id not in group_ids) or (
            c.kind == "person" and c.id not in person_ids
        ):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unbekannte Freigabe")
        wanted[c.host_id][0 if c.kind == "group" else 1].append(c.id)

    changed = []
    for hid, host in hosts.items():
        before = snapshot(host)
        set_grants(host, *wanted[hid])
        db.flush()
        db.refresh(host, ["grants"])
        changes = diff(before, snapshot(host))
        if changes:
            host.version += 1
            add_version(db, host, actor=actor.name, comment="Zugriffsmatrix")
            audit.record(
                db,
                actor=actor.name,
                action="access_changed",
                target=host.domain,
                details={"version": host.version, "changes": changes},
                ip=actor.ip,
            )
            changed.append(host.domain)
    db.commit()
    errors = apply_all(db, settings, request.app.state.caddy_transport) if changed else []
    db.commit()
    return {"changed": changed, "ok": not errors, "error": "; ".join(errors) or None}
