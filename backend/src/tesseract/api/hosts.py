import asyncio
import ipaddress
import re
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract import audit, checks
from tesseract.api.iplists import normalize_networks
from tesseract.caddy.config import covering_wildcard, host_route, is_public_name
from tesseract.db.models import (
    CustomCert,
    Group,
    Host,
    HostArea,
    HostVersion,
    IpList,
    Node,
    Person,
)
from tesseract.deps import DB, AppSettings, CurrentActor
from tesseract.services import (
    add_version,
    allowed_devices,
    apply_node,
    apply_snapshot,
    diff,
    get_general,
    granted_persons,
    host_spec,
    set_grants,
    set_paths,
    snapshot,
)

router = APIRouter(prefix="/hosts", tags=["hosts"])

_LABEL = r"(?!-)[a-z0-9-]{1,63}(?<!-)"
DOMAIN_RE = re.compile(rf"^(?=.{{1,253}}$)({_LABEL}\.)*{_LABEL}$")
PATH_RE = re.compile(r"^/[A-Za-z0-9/_\-.~%*]*$")
MAX_PATHS = 32


def normalize_domain(value: str, allow_wildcard: bool = False) -> str:
    value = value.strip().lower().rstrip(".")
    if allow_wildcard and value.startswith("*."):
        return "*." + normalize_domain(value[2:])
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


def _clean_paths(v: list[str]) -> list[str]:
    out = []
    for p in v:
        p = p.strip()
        if not p:
            continue
        if not p.startswith("/"):
            p = "/" + p
        if len(p) > 255 or not PATH_RE.match(p):
            raise ValueError(f"Ungültiger Pfad: {p}")
        out.append(p)
    return list(dict.fromkeys(out))


class AreaIn(BaseModel):
    """Bereich mit abweichenden Regeln. None = wie beim Host."""

    name: str = Field("", max_length=64)
    paths: list[str] = Field(min_length=1, max_length=MAX_PATHS)
    access: Literal["public", "mtls"] | None = None
    grant_group_ids: list[int] = Field(default_factory=list)
    grant_person_ids: list[int] = Field(default_factory=list)
    waf_mode: Literal["off", "detect", "block"] | None = None
    waf_exclusions: list[int] = Field(default_factory=list, max_length=200)
    authelia: bool | None = None
    ip_mode: Literal["off", "block", "allow"] | None = None
    ip_entries: list[str] = Field(default_factory=list, max_length=500)
    ip_list_ids: list[int] = Field(default_factory=list, max_length=50)

    @field_validator("paths")
    @classmethod
    def _paths(cls, v: list[str]) -> list[str]:
        out = _clean_paths(v)
        if not out:
            raise ValueError("Ein Bereich braucht mindestens einen Pfad")
        return out

    @field_validator("ip_entries")
    @classmethod
    def _ip_entries(cls, v: list[str]) -> list[str]:
        return normalize_networks(v)

    @field_validator("waf_exclusions")
    @classmethod
    def _exclusions(cls, v: list[int]) -> list[int]:
        for rule_id in v:
            if not 1 <= rule_id <= 99_999_999:
                raise ValueError(f"Ungültige Regel-ID: {rule_id}")
        return sorted(set(v))

    @model_validator(mode="after")
    def _allow_needs_entries(self) -> "AreaIn":
        if self.ip_mode == "allow" and not self.ip_entries and not self.ip_list_ids:
            raise ValueError("„Nur erlauben“ braucht mindestens eine IP, ein Netz oder eine Liste")
        return self


class AreaOut(AreaIn):
    id: int


class HostIn(BaseModel):
    domain: str
    node_id: int
    upstream_scheme: Literal["http", "https"] = "http"
    upstream_host: str
    upstream_port: int = Field(ge=1, le=65535)
    # nur bei https: Zertifikat des Ziels nicht prüfen
    upstream_insecure: bool = False
    websockets: bool = True
    force_https: bool = True
    compression: bool = False
    access: Literal["public", "mtls"] = "public"
    no_cert_action: Literal["reject", "hint"] = "reject"
    # bei "public": diese Pfade nur mit Zertifikat · bei "mtls": diese Pfade öffentlich
    paths: list[str] = Field(default_factory=list, max_length=MAX_PATHS)
    grant_group_ids: list[int] = Field(default_factory=list)
    grant_person_ids: list[int] = Field(default_factory=list)
    # None = Standard aus den Einstellungen (nur beim Anlegen)
    waf_mode: Literal["off", "detect", "block"] | None = None
    waf_paranoia: int | None = Field(None, ge=1, le=4)
    waf_exclusions: list[int] = Field(default_factory=list, max_length=200)
    ip_mode: Literal["off", "block", "allow"] = "off"
    ip_entries: list[str] = Field(default_factory=list, max_length=500)
    ip_list_ids: list[int] = Field(default_factory=list, max_length=50)
    authelia: bool = False
    tls_challenge: Literal["http", "dns"] = "http"
    internal: bool = False
    custom_cert_id: int | None = None
    areas: list[AreaIn] = Field(default_factory=list, max_length=20)
    enabled: bool = True
    draft: bool = False
    comment: str = Field("", max_length=255)

    @field_validator("ip_entries")
    @classmethod
    def _ip_entries(cls, v: list[str]) -> list[str]:
        return normalize_networks(v)

    @model_validator(mode="after")
    def _allow_needs_entries(self) -> "HostIn":
        if self.ip_mode == "allow" and not self.ip_entries and not self.ip_list_ids:
            raise ValueError("„Nur erlauben“ braucht mindestens eine IP, ein Netz oder eine Liste")
        return self

    @field_validator("waf_exclusions")
    @classmethod
    def _exclusions(cls, v: list[int]) -> list[int]:
        for rule_id in v:
            if not 1 <= rule_id <= 99_999_999:
                raise ValueError(f"Ungültige Regel-ID: {rule_id}")
        return sorted(set(v))

    @field_validator("paths")
    @classmethod
    def _paths(cls, v: list[str]) -> list[str]:
        return _clean_paths(v)

    @field_validator("domain")
    @classmethod
    def _domain(cls, v: str) -> str:
        return normalize_domain(v, allow_wildcard=True)

    @model_validator(mode="after")
    def _wildcard_needs_dns(self) -> "HostIn":
        if self.domain.startswith("*.") and self.tls_challenge != "dns":
            raise ValueError("Wildcard-Domains brauchen die DNS-Prüfung (DNS-01)")
        return self

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


class GrantRef(BaseModel):
    kind: Literal["group", "person"]
    id: int
    name: str


class HostOut(BaseModel):
    id: int
    domain: str
    node: NodeRef
    upstream_scheme: str
    upstream_host: str
    upstream_port: int
    upstream_insecure: bool
    websockets: bool
    force_https: bool
    compression: bool
    access: str
    no_cert_action: str
    waf_mode: str
    waf_paranoia: int
    waf_exclusions: list[int]
    ip_mode: str
    ip_entries: list[str]
    ip_list_ids: list[int]
    authelia: bool
    tls_challenge: str
    internal: bool
    custom_cert_id: int | None
    # Geteiltes Wildcard-Zertifikat, das diesen Host abdeckt (sonst None)
    wildcard_cert: str | None
    areas: list[AreaOut]
    paths: list[str]
    grants: list[GrantRef]
    granted_persons: int
    allowed_devices: int
    enabled: bool
    draft: bool
    # Herkunft: "ui" oder "docker"; bei Docker der Container (Node-ID:Name)
    source: str = "ui"
    source_ref: str | None = None
    # von der Docker-Anbindung abgeschaltet (Container gestoppt/entfernt)
    source_disabled: bool = False
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


_COMPUTED = {
    "node",
    "paths",
    "grants",
    "granted_persons",
    "allowed_devices",
    "areas",
    "wildcard_cert",
}


def _out(db: Session, host: Host) -> HostOut:
    grants = [
        GrantRef(kind="group", id=g.group.id, name=g.group.name)
        if g.group is not None
        else GrantRef(kind="person", id=g.person.id, name=g.person.name)
        for g in host.grants
        if g.group is not None or g.person is not None
    ]
    grants.sort(key=lambda g: (g.kind != "group", g.name.lower()))
    data = {c: getattr(host, c) for c in HostOut.model_fields if c not in _COMPUTED}
    return HostOut(
        **data,
        node=NodeRef(id=host.node.id, name=host.node.name),
        paths=[p.path for p in host.paths],
        areas=[
            AreaOut.model_validate(
                {
                    **{k: getattr(a, k) for k in AreaIn.model_fields},
                    "id": a.id,
                    "grant_group_ids": a.grant_group_ids or [],
                    "grant_person_ids": a.grant_person_ids or [],
                    "waf_exclusions": a.waf_exclusions or [],
                    "ip_entries": a.ip_entries or [],
                    "ip_list_ids": a.ip_list_ids or [],
                }
            )
            for a in host.areas
        ],
        grants=grants,
        wildcard_cert=covering_wildcard(host.domain, get_general(db)["wildcard_certs"]),
        granted_persons=len(granted_persons(db, host)),
        allowed_devices=len(allowed_devices(db, host)),
    )


def _check_ip_lists(db: Session, body: HostIn) -> None:
    for area in body.areas:
        for i in area.ip_list_ids:
            if db.get(IpList, i) is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, f"IP-Liste {i} unbekannt"
                )
        for model, ids, what in (
            (Group, area.grant_group_ids, "Gruppe"),
            (Person, area.grant_person_ids, "Person"),
        ):
            for i in ids:
                if db.get(model, i) is None:
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_CONTENT, f"{what} {i} unbekannt"
                    )
        if area.authelia and not get_general(db)["authelia_url"]:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Erst unter Einstellungen › Integrationen die Authelia-Adresse eintragen",
            )
    for i in body.ip_list_ids:
        if db.get(IpList, i) is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"IP-Liste {i} unbekannt")


def _check_grants(db: Session, body: HostIn) -> None:
    _check_ip_lists(db, body)
    general = get_general(db)
    if body.internal and not (general["internal_networks"] or general["internal_list_ids"]):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Erst unter Einstellungen › Integrationen die internen Netze festlegen",
        )
    if body.custom_cert_id is not None and db.get(CustomCert, body.custom_cert_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Zertifikat unbekannt")
    covered = covering_wildcard(body.domain, general["wildcard_certs"]) or body.custom_cert_id
    if (
        body.internal
        and body.tls_challenge == "http"
        and is_public_name(body.domain)
        and not covered
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Interne Hosts sind von außen nicht erreichbar – das Zertifikat braucht DNS-01",
        )
    if (
        body.tls_challenge == "dns"
        and not general["cloudflare_token_enc"]
        and not body.custom_cert_id
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Für DNS-01 erst unter Einstellungen › Integrationen den Cloudflare-Token eintragen",
        )
    if body.authelia and not get_general(db)["authelia_url"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Erst unter Einstellungen › Integrationen die Authelia-Adresse eintragen",
        )
    for model, ids, what in (
        (Group, body.grant_group_ids, "Gruppe"),
        (Person, body.grant_person_ids, "Person"),
    ):
        for i in ids:
            if db.get(model, i) is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{what} {i} unbekannt")


_RELATIONS = {"comment", "paths", "grant_group_ids", "grant_person_ids", "areas"}


def _assign(host: Host, body: HostIn, defaults: dict[str, Any] | None = None) -> None:
    data = body.model_dump(exclude=_RELATIONS)
    # Nicht angegebene WAF-Werte: beim Anlegen Standard, beim Ändern unverändert
    if data["waf_mode"] is None:
        data["waf_mode"] = (defaults or {}).get("waf_default_mode", host.waf_mode or "off")
    if data["waf_paranoia"] is None:
        data["waf_paranoia"] = (defaults or {}).get("waf_default_paranoia", host.waf_paranoia or 1)
    for k, v in data.items():
        setattr(host, k, v)
    set_paths(host, body.paths)
    set_grants(host, body.grant_group_ids, body.grant_person_ids)
    host.areas = [HostArea(position=i, **a.model_dump()) for i, a in enumerate(body.areas)]


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


WAF_MODULE = "http.handlers.waf"
DNS_MODULE = "dns.providers.cloudflare"


def _check_modules(node: Node, host: Host) -> None:
    """Fehlt dem Node ein Modul, würde Caddy die ganze Config ablehnen – dann lieber gleich
    hier mit verständlicher Meldung. Nur, wenn die Module des Nodes schon bekannt sind."""
    if node.modules is None or host.draft or not host.enabled:
        return
    missing = []
    waf = host.waf_mode != "off" or any(a.waf_mode not in (None, "off") for a in host.areas)
    if waf and WAF_MODULE not in node.modules:
        missing.append("Coraza WAF (WAF für diesen Host ausschalten)")
    dns = host.tls_challenge == "dns" or host.domain.startswith("*.")
    if dns and DNS_MODULE not in node.modules:
        missing.append("DNS Cloudflare (Prüfung auf HTTP-01 stellen)")
    if missing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Dem Caddy auf Node „{node.name}“ fehlt: {'; '.join(missing)}. "
            "Abhilfe: Image tesseract-caddy auf dem Node verwenden.",
        )


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
    return [_out(db, h) for h in db.scalars(select(Host).order_by(Host.domain))]


def _node_ips(db: Session, node_id: int | None) -> tuple[list[str], str]:
    """Öffentliche IPs des Nodes, auf dem der Host laufen soll (ohne Angabe: der lokale)."""
    node = db.get(Node, node_id) if node_id else None
    if node is None:
        node = db.scalar(select(Node).where(Node.kind == "local").order_by(Node.id))
    if node is None:
        return [], ""
    return list(node.public_ips or []), node.name


async def _upstream_check(request: Request, db: Session, node_id: int | None, host: str, port: int):
    """Erreichbarkeit des Ziels – vom Node aus, wenn es ein Agent-Node ist (ab Agent 1.1)."""
    from tesseract import nodes as node_svc
    from tesseract.agent_tasks import supports_tasks

    node = db.get(Node, node_id) if node_id else None
    if node is None or not node.is_agent:
        return await asyncio.to_thread(checks.check_upstream, host, port)
    title = "Ziel erreichbar"
    if not supports_tasks(node) or node_svc.state(node) in ("offline", "pending"):
        why = "offline" if node_svc.state(node) == "offline" else "Agent älter als 1.1"
        c = await asyncio.to_thread(checks.check_upstream, host, port)
        return checks.Check(
            "upstream", title, "info", f"Nicht vom Node „{node.name}“ prüfbar ({why}) – {c.detail}"
        )
    if host in ("localhost", "::1") or host.startswith("127."):
        return checks.Check(
            "upstream",
            title,
            "info",
            f"{host} meint den Rechner von Caddy – vom Agent aus nicht sinnvoll prüfbar "
            "(eigener Container). Gilt Caddy im Host-Netz, ist das so in Ordnung.",
        )
    r = await request.app.state.agent_tasks.run(
        node.id, "tcp", {"host": host, "port": port, "timeout": 3}, timeout=8
    )
    if r is None:
        return checks.Check("upstream", title, "warn", f"Node „{node.name}“ hat nicht geantwortet")
    if r.get("ok"):
        return checks.Check(
            "upstream",
            title,
            "ok",
            f"{host}:{port} antwortet dem Node „{node.name}“ · {r.get('ms', '?')} ms",
        )
    return checks.Check(
        "upstream",
        title,
        "warn",
        f"{host}:{port} vom Node „{node.name}“ aus nicht erreichbar ({r.get('error', '?')})",
    )


@router.post("/check")
async def run_checks(
    body: CheckIn, request: Request, db: DB, _: CurrentActor, settings: AppSettings
) -> list[dict]:
    try:
        domain = normalize_domain(body.domain, allow_wildcard=True)
    except ValueError as e:
        return [checks.Check("domain", "Domain", "bad", str(e)).dict()]
    result = [
        checks.check_domain_free(db, domain, body.exclude_id, settings.controller_domain),
        # Bei Wildcards einen Beispielnamen prüfen; verglichen wird mit den IPs des gewählten Nodes
        checks.check_dns(domain.replace("*.", "test.", 1), *_node_ips(db, body.node_id)),
    ]
    if body.upstream_host and body.upstream_port:
        try:
            upstream = normalize_upstream_host(body.upstream_host)
            result.append(
                await _upstream_check(request, db, body.node_id, upstream, body.upstream_port)
            )
        except ValueError as e:
            result.append(checks.Check("upstream", "Ziel erreichbar", "bad", str(e)))
    result.append(checks.check_port80_hint(domain))
    return [c.dict() for c in result]


@router.post("/preview")
def preview_route(body: HostIn, _: CurrentActor) -> dict[str, Any]:
    """Caddy-Route, wie sie für diesen Host erzeugt würde."""
    return host_route(host_spec(body, host_id=0, paths=body.paths))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_host(
    body: HostIn, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> HostSaved:
    _get_node(db, body.node_id)
    _check_grants(db, body)
    _ensure_free(db, body.domain, None, settings.controller_domain)
    host = Host(version=1)
    _assign(host, body, get_general(db))
    _check_modules(_get_node(db, body.node_id), host)
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
    return HostSaved(host=_out(db, host), apply=result)


@router.get("/{host_id}")
def get_host(host_id: int, db: DB, _: CurrentActor) -> HostOut:
    return _out(db, _get_host(db, host_id))


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
    _check_grants(db, body)
    _ensure_free(db, body.domain, host.id, settings.controller_domain)
    before = snapshot(host)
    old_node = host.node_id
    _assign(host, body)
    try:
        _check_modules(_get_node(db, body.node_id), host)
    except HTTPException:
        db.rollback()
        raise
    db.flush()
    db.refresh(host, ["node", "paths", "grants", "areas"])
    changes = diff(before, snapshot(host))
    if not changes:
        db.rollback()
        return HostSaved(host=_out(db, host), apply=ApplyResult(ok=True, skipped=True))
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
    return HostSaved(host=_out(db, host), apply=result)


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
    """Route eines alten Stands (ohne Geräteliste – die ändert sich laufend)."""
    skip = {"node", "enabled", "draft", "grants", "ip_lists", "areas"}
    fields = {k: snap[k] for k in snap if k not in skip}
    if fields.get("waf_mode") is None:
        fields.pop("waf_mode", None)
    paths = list(fields.pop("paths", []))
    spec = host_spec(HostIn.model_construct(**fields), host_id=host_id, paths=paths)
    return host_route(spec)


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
    missing = apply_snapshot(db, host, old.snapshot)
    host.version += 1
    add_version(db, host, actor=actor.name, comment=f"Zurückgesetzt auf Version {version}")
    audit.record(
        db,
        actor=actor.name,
        action="host_restored",
        target=host.domain,
        details={"from_version": version, "version": host.version, "missing_grants": missing},
        ip=actor.ip,
    )
    db.commit()
    result = _apply(request, db, {old_node, host.node_id}, settings)
    db.commit()
    return HostSaved(host=_out(db, host), apply=result)
