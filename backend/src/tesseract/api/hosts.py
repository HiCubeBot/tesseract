import ipaddress
import re
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract import audit, checks
from tesseract.caddy.config import host_route
from tesseract.db.models import Host, HostVersion, Node
from tesseract.deps import DB, AppSettings, CurrentActor
from tesseract.services import (
    add_version,
    apply_node,
    apply_snapshot,
    diff,
    get_general,
    host_spec,
    snapshot,
)

router = APIRouter(prefix="/hosts", tags=["hosts"])

_LABEL = r"(?!-)[a-z0-9-]{1,63}(?<!-)"
DOMAIN_RE = re.compile(rf"^(?=.{{1,253}}$)({_LABEL}\.)*{_LABEL}$")


def normalize_domain(value: str) -> str:
    value = value.strip().lower().rstrip(".")
    try:
        value = value.encode("idna").decode("ascii")
    except UnicodeError as e:
        raise ValueError("Ungültiger Domainname") from e
    if not DOMAIN_RE.match(value):
        raise ValueError("Ungültiger Domainname")
    return value


def normalize_upstream_host(value: str) -> str:
    value = value.strip().strip("[]")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        pass
    if "/" in value or ":" in value:
        raise ValueError("Nur Hostname oder IP – Protokoll und Port separat angeben")
    return normalize_domain(value)


class HostIn(BaseModel):
    domain: str
    node_id: int
    upstream_scheme: Literal["http", "https"] = "http"
    upstream_host: str
    upstream_port: int = Field(ge=1, le=65535)
    websockets: bool = True
    force_https: bool = True
    compression: bool = False
    access: Literal["public"] = "public"  # "mtls" folgt in Phase 2
    enabled: bool = True
    draft: bool = False
    comment: str = Field("", max_length=255)

    @field_validator("domain")
    @classmethod
    def _domain(cls, v: str) -> str:
        return normalize_domain(v)

    @field_validator("upstream_host")
    @classmethod
    def _upstream(cls, v: str) -> str:
        return normalize_upstream_host(v)


class CheckIn(BaseModel):
    domain: str
    node_id: int | None = None
    upstream_host: str = ""
    upstream_port: int | None = Field(None, ge=1, le=65535)
    exclude_id: int | None = None


class NodeRef(BaseModel):
    id: int
    name: str


class HostOut(BaseModel):
    id: int
    domain: str
    node: NodeRef
    upstream_scheme: str
    upstream_host: str
    upstream_port: int
    websockets: bool
    force_https: bool
    compression: bool
    access: str
    enabled: bool
    draft: bool
    version: int
    created_at: datetime
    updated_at: datetime


class ApplyResult(BaseModel):
    ok: bool
    error: str | None = None
    skipped: bool = False


class HostSaved(BaseModel):
    host: HostOut
    apply: ApplyResult


class VersionOut(BaseModel):
    version: int
    created_at: datetime
    actor: str
    comment: str
    current: bool
    changes: list[dict[str, Any]]
    snapshot: dict[str, Any]


class VersionDetail(VersionOut):
    route: dict[str, Any]
    previous_route: dict[str, Any] | None


def _out(host: Host) -> HostOut:
    return HostOut.model_validate(
        {**{c: getattr(host, c) for c in HostOut.model_fields if c != "node"}, "node": host.node},
        from_attributes=True,
    )


def _get_host(db: Session, host_id: int) -> Host:
    host = db.get(Host, host_id)
    if host is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Host nicht gefunden")
    return host


def _get_node(db: Session, node_id: int) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Node nicht gefunden")
    return node


def _ensure_free(db: Session, domain: str, exclude_id: int | None, controller_domain: str) -> None:
    c = checks.check_domain_free(db, domain, exclude_id, controller_domain)
    if c.status == "bad":
        raise HTTPException(status.HTTP_409_CONFLICT, c.detail)


def _apply(request: Request, db: Session, nodes: set[int], settings: Any) -> ApplyResult:
    errors = []
    for node_id in sorted(nodes):
        node = db.get(Node, node_id)
        if node is None:
            continue
        err = apply_node(db, node, settings, request.app.state.caddy_transport)
        if err:
            errors.append(f"{node.name}: {err}")
    return ApplyResult(ok=not errors, error="; ".join(errors) or None)


@router.get("")
def list_hosts(db: DB, _: CurrentActor) -> list[HostOut]:
    return [_out(h) for h in db.scalars(select(Host).order_by(Host.domain))]


@router.post("/check")
def run_checks(body: CheckIn, db: DB, _: CurrentActor, settings: AppSettings) -> list[dict]:
    try:
        domain = normalize_domain(body.domain)
    except ValueError as e:
        return [checks.Check("domain", "Domain", "bad", str(e)).dict()]
    result = [
        checks.check_domain_free(db, domain, body.exclude_id, settings.controller_domain),
        checks.check_dns(domain, list(get_general(db)["public_ips"])),
    ]
    if body.upstream_host and body.upstream_port:
        try:
            upstream = normalize_upstream_host(body.upstream_host)
            result.append(checks.check_upstream(upstream, body.upstream_port))
        except ValueError as e:
            result.append(checks.Check("upstream", "Ziel erreichbar", "bad", str(e)))
    result.append(checks.check_port80_hint(domain))
    return [c.dict() for c in result]


@router.post("/preview")
def preview_route(body: HostIn, _: CurrentActor) -> dict[str, Any]:
    """Caddy-Route, wie sie für diesen Host erzeugt würde."""
    return host_route(host_spec(body, host_id=0))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_host(
    body: HostIn, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> HostSaved:
    _get_node(db, body.node_id)
    _ensure_free(db, body.domain, None, settings.controller_domain)
    host = Host(**body.model_dump(exclude={"comment"}), version=1)
    db.add(host)
    add_version(db, host, actor=actor.name, comment=body.comment or "Angelegt")
    audit.record(
        db,
        actor=actor.name,
        action="host_created",
        target=host.domain,
        details=snapshot(host),
        ip=actor.ip,
    )
    db.commit()
    result = (
        ApplyResult(ok=True, skipped=True)
        if host.draft
        else _apply(request, db, {host.node_id}, settings)
    )
    db.commit()
    return HostSaved(host=_out(host), apply=result)


@router.get("/{host_id}")
def get_host(host_id: int, db: DB, _: CurrentActor) -> HostOut:
    return _out(_get_host(db, host_id))


@router.put("/{host_id}")
def update_host(
    host_id: int,
    body: HostIn,
    request: Request,
    db: DB,
    actor: CurrentActor,
    settings: AppSettings,
) -> HostSaved:
    host = _get_host(db, host_id)
    _get_node(db, body.node_id)
    _ensure_free(db, body.domain, host.id, settings.controller_domain)
    before = snapshot(host)
    old_node = host.node_id
    for k, v in body.model_dump(exclude={"comment"}).items():
        setattr(host, k, v)
    db.flush()
    db.refresh(host, ["node"])
    changes = diff(before, snapshot(host))
    if not changes:
        return HostSaved(host=_out(host), apply=ApplyResult(ok=True, skipped=True))
    host.version += 1
    add_version(db, host, actor=actor.name, comment=body.comment)
    audit.record(
        db,
        actor=actor.name,
        action="host_updated",
        target=host.domain,
        details={"version": host.version, "changes": changes},
        ip=actor.ip,
    )
    db.commit()
    result = _apply(request, db, {old_node, host.node_id}, settings)
    db.commit()
    return HostSaved(host=_out(host), apply=result)


@router.delete("/{host_id}")
def delete_host(
    host_id: int, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> ApplyResult:
    host = _get_host(db, host_id)
    node_id, domain = host.node_id, host.domain
    db.delete(host)
    audit.record(db, actor=actor.name, action="host_deleted", target=domain, ip=actor.ip)
    db.commit()
    result = _apply(request, db, {node_id}, settings)
    db.commit()
    return result


def _versions(host: Host) -> list[VersionOut]:
    out = []
    prev: dict[str, Any] | None = None
    for v in host.versions:
        out.append(
            VersionOut(
                version=v.version,
                created_at=v.created_at,
                actor=v.actor,
                comment=v.comment,
                current=v.version == host.version,
                changes=diff(prev, v.snapshot),
                snapshot=v.snapshot,
            )
        )
        prev = v.snapshot
    return list(reversed(out))


@router.get("/{host_id}/versions")
def list_versions(host_id: int, db: DB, _: CurrentActor) -> list[VersionOut]:
    return _versions(_get_host(db, host_id))


def _route_for(snap: dict[str, Any], host_id: int) -> dict[str, Any]:
    fields = {k: snap[k] for k in snap if k not in {"node", "access", "enabled", "draft"}}
    return host_route(host_spec(HostIn.model_construct(**fields), host_id=host_id))


@router.get("/{host_id}/versions/{version}")
def get_version(host_id: int, version: int, db: DB, _: CurrentActor) -> VersionDetail:
    host = _get_host(db, host_id)
    versions = {v.version: v for v in _versions(host)}
    if version not in versions:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version nicht gefunden")
    v = versions[version]
    prev = versions.get(version - 1)
    return VersionDetail(
        **v.model_dump(),
        route=_route_for(v.snapshot, host.id),
        previous_route=_route_for(prev.snapshot, host.id) if prev else None,
    )


@router.post("/{host_id}/versions/{version}/restore")
def restore_version(
    host_id: int,
    version: int,
    request: Request,
    db: DB,
    actor: CurrentActor,
    settings: AppSettings,
) -> HostSaved:
    host = _get_host(db, host_id)
    old = db.scalar(
        select(HostVersion).where(HostVersion.host_id == host.id, HostVersion.version == version)
    )
    if old is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version nicht gefunden")
    if old.version == host.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "Das ist bereits die laufende Version")
    _ensure_free(db, old.snapshot["domain"], host.id, settings.controller_domain)
    old_node = host.node_id
    apply_snapshot(db, host, old.snapshot)
    host.version += 1
    add_version(db, host, actor=actor.name, comment=f"Zurückgesetzt auf Version {version}")
    audit.record(
        db,
        actor=actor.name,
        action="host_restored",
        target=host.domain,
        details={"from_version": version, "version": host.version},
        ip=actor.ip,
    )
    db.commit()
    result = _apply(request, db, {old_node, host.node_id}, settings)
    db.commit()
    return HostSaved(host=_out(host), apply=result)
