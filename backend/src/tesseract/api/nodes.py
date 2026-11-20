import ipaddress
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from tesseract import audit
from tesseract import nodes as node_svc
from tesseract.caddy.config import redact
from tesseract.db.models import Host, Node
from tesseract.deps import DB, AppSettings, Box, CurrentActor
from tesseract.identity import CAError, ca_configured
from tesseract.services import apply_node, get_general, node_config, node_in_sync

router = APIRouter(prefix="/nodes", tags=["nodes"])


class NodeOut(BaseModel):
    id: int
    name: str
    location: str
    kind: str
    public_ips: list[str]
    # pending | online | offline | drift | error
    state: str
    hosts: int
    last_applied_at: datetime | None
    last_apply_error: str | None
    in_sync: bool
    last_seen_at: datetime | None
    agent_version: str | None
    caddy_version: str | None
    modules: list[str] | None
    drift: bool
    drift_since: datetime | None
    accepted: bool
    # Beitritt
    join_state: str | None
    join_open: bool
    join_expires_at: datetime | None
    join_hostname: str | None
    join_key_fingerprint: str | None
    join_requested_at: datetime | None
    cert_not_after: datetime | None


class JoinToken(BaseModel):
    token: str
    expires_at: datetime
    # Agent ohne Docker-Vorlage (Kommandozeile)
    command: str
    # Ein Befehl für den neuen Server: lädt das Installationsskript vom Controller
    install_command: str
    install_sha256: str


class NodeCreated(BaseModel):
    node: NodeOut
    join: JoinToken


class NodeIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    location: str = Field(default="", max_length=128)
    # None = unverändert lassen
    public_ips: list[str] | None = Field(default=None, max_length=16)

    @field_validator("public_ips")
    @classmethod
    def _ips(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out: list[str] = []
        for raw in v:
            if not raw.strip():
                continue
            try:
                ip = str(ipaddress.ip_address(raw.strip()))
            except ValueError as e:
                raise ValueError(f"„{raw.strip()}“ ist keine IP-Adresse") from e
            if ip not in out:
                out.append(ip)
        return out


def _get(db, node_id: int) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Node nicht gefunden")
    return node


def _agent(db, node_id: int) -> Node:
    node = _get(db, node_id)
    if not node.is_agent:
        raise HTTPException(status.HTTP_409_CONFLICT, "Der lokale Node hat keinen Agent")
    return node


def _out(db, node: Node, settings, hosts: int | None = None) -> NodeOut:
    if hosts is None:
        hosts = db.scalar(select(func.count()).where(Host.node_id == node.id)) or 0
    now = node_svc.utcnow()
    return NodeOut(
        id=node.id,
        name=node.name,
        location=node.location,
        kind=node.kind,
        public_ips=node.public_ips or [],
        state=node_svc.state(node, now),
        hosts=hosts,
        last_applied_at=node.last_applied_at,
        last_apply_error=node.last_apply_error,
        in_sync=node.joined and node_in_sync(db, node, settings),
        last_seen_at=node.last_seen_at,
        agent_version=node.agent_version,
        caddy_version=node.caddy_version,
        modules=node.modules,
        drift=node.drift,
        drift_since=node.drift_since,
        accepted=node.accepted_hash is not None and node.running_hash == node.accepted_hash,
        join_state=node.join_state,
        join_open=node.join_token_hash is not None
        and node.join_expires_at is not None
        and node.join_expires_at > now,
        join_expires_at=node.join_expires_at,
        join_hostname=node.join_hostname,
        join_key_fingerprint=node.join_key_fp,
        join_requested_at=node.join_requested_at,
        cert_not_after=node.cert_not_after,
    )


def _controller_url(request: Request, settings) -> str:
    if settings.controller_domain:
        return f"https://{settings.controller_domain}"
    return str(request.base_url).rstrip("/")


def _join(request: Request, db, settings, token: str, node: Node) -> JoinToken:
    from tesseract.api.install import install_info

    url = _controller_url(request, settings)
    info = install_info(request, db, token)
    return JoinToken(
        token=token,
        expires_at=node.join_expires_at,
        command=f"tesseract-agent join --controller {url} --token {token}",
        install_command=info["command"],
        install_sha256=info["sha256"],
    )


@router.get("")
def list_nodes(db: DB, _: CurrentActor, settings: AppSettings) -> list[NodeOut]:
    counts = dict(db.execute(select(Host.node_id, func.count()).group_by(Host.node_id)).all())
    return [
        _out(db, n, settings, counts.get(n.id, 0))
        for n in db.scalars(select(Node).order_by(Node.name))
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_node(
    body: NodeIn, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> NodeCreated:
    """Neuer Node mit Agent – liefert ein Beitritts-Token (30 Min., einmalig)."""
    try:
        name = node_svc.normalize_name(body.name)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    if not ca_configured(db):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Erst die Zertifizierungsstelle einrichten – sie signiert die Node-Zertifikate",
        )
    if db.scalar(select(Node).where(Node.name == name)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Node „{name}“ gibt es schon")
    node = Node(name=name, location=body.location.strip(), kind="agent", admin_url="")
    token = node_svc.new_join_token(node)
    db.add(node)
    audit.record(db, actor=actor.name, action="node_created", target=name, ip=actor.ip)
    db.commit()
    return NodeCreated(
        node=_out(db, node, settings, 0), join=_join(request, db, settings, token, node)
    )


@router.put("/{node_id}")
def update_node(
    node_id: int,
    body: NodeIn,
    request: Request,
    db: DB,
    actor: CurrentActor,
    settings: AppSettings,
) -> NodeOut:
    node = _get(db, node_id)
    try:
        name = node_svc.normalize_name(body.name)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    if name != node.name and db.scalar(select(Node).where(Node.name == name)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Node „{name}“ gibt es schon")
    if name != node.name and not node.is_agent:
        raise HTTPException(status.HTTP_409_CONFLICT, "Der lokale Node behält seinen Namen")
    new = {"name": name, "location": body.location.strip()}
    if body.public_ips is not None:
        new["public_ips"] = body.public_ips
    old = {"name": node.name, "location": node.location, "public_ips": node.public_ips or []}
    changes = {k: [old[k], v] for k, v in new.items() if old[k] != v}
    for k, v in new.items():
        setattr(node, k, v)
    if changes:
        audit.record(
            db, actor=actor.name, action="node_updated", target=name, details=changes, ip=actor.ip
        )
    db.commit()
    if "public_ips" in changes:
        _follow_ips(request, db, node, settings)
    return _out(db, node, settings)


def _follow_ips(request: Request, db, node: Node, settings) -> None:
    """Neue öffentliche IPs → A/AAAA-Einträge, die darauf zeigen, nachziehen."""
    from tesseract import dnsrecords as dr
    from tesseract.db.models import Host

    transport = getattr(request.app.state, "dns_transport", None)
    for h in db.scalars(select(Host).where(Host.node_id == node.id, Host.dns_type == "address")):
        if not (h.dns_target or "").strip():
            dr.apply_host(db, h, settings, transport)
    if not node.is_agent:
        cfg = dr.controller_config(get_general(db))
        if cfg["type"] == "address" and not cfg["target"]:
            dr.apply_controller(db, settings, transport)


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(node_id: int, db: DB, actor: CurrentActor) -> None:
    node = _agent(db, node_id)
    if db.scalar(select(func.count()).where(Host.node_id == node.id)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Dem Node sind noch Hosts zugeordnet – erst umziehen"
        )
    audit.record(db, actor=actor.name, action="node_deleted", target=node.name, ip=actor.ip)
    db.delete(node)
    db.commit()


@router.post("/{node_id}/token")
def new_token(
    node_id: int, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> JoinToken:
    """Neues Beitritts-Token, z. B. wenn der Agent neu aufgesetzt wurde."""
    node = _agent(db, node_id)
    token = node_svc.new_join_token(node)
    audit.record(db, actor=actor.name, action="node_token_created", target=node.name, ip=actor.ip)
    db.commit()
    return _join(request, db, settings, token, node)


@router.post("/{node_id}/approve")
def approve(node_id: int, db: DB, box: Box, actor: CurrentActor, settings: AppSettings) -> NodeOut:
    node = _agent(db, node_id)
    try:
        node_svc.approve_join(db, box, node)
    except (ValueError, CAError) as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    audit.record(
        db,
        actor=actor.name,
        action="node_approved",
        target=node.name,
        details={"key": node.join_key_fp, "hostname": node.join_hostname},
        ip=actor.ip,
    )
    db.commit()
    return _out(db, node, settings)


@router.post("/{node_id}/reject")
def reject(node_id: int, db: DB, actor: CurrentActor, settings: AppSettings) -> NodeOut:
    node = _agent(db, node_id)
    try:
        node_svc.reject_join(node)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    audit.record(db, actor=actor.name, action="node_rejected", target=node.name, ip=actor.ip)
    db.commit()
    return _out(db, node, settings)


@router.get("/{node_id}/config")
def get_config(node_id: int, db: DB, _: CurrentActor, settings: AppSettings) -> dict[str, Any]:
    """Die Caddy-Config, die der Controller für diesen Node erzeugt (ohne Geheimnisse)."""
    return redact(node_config(db, _get(db, node_id), settings))


@router.get("/{node_id}/drift")
def get_drift(node_id: int, db: DB, _: CurrentActor, settings: AppSettings) -> dict[str, Any]:
    """Unterschiede zwischen der laufenden Config und dem Stand des Controllers."""
    node = _get(db, node_id)
    if not node.drift or node.running_config is None:
        return {"drift": False, "since": None, "changes": []}
    expected = redact(node_config(db, node, settings))
    running = redact(node.running_config)
    changes = node_svc.json_diff(expected, running)[:200]
    for c in changes:
        c["host"] = node_svc.route_host(running, c["path"]) or node_svc.route_host(
            expected, c["path"]
        )
    return {"drift": True, "since": node.drift_since, "changes": changes}


@router.post("/{node_id}/apply")
def apply(
    node_id: int, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> dict[str, Any]:
    node = _get(db, node_id)
    if not node.joined:
        raise HTTPException(status.HTTP_409_CONFLICT, "Der Node ist noch nicht beigetreten")
    err = apply_node(db, node, settings, request.app.state.caddy_transport)
    audit.record(
        db,
        actor=actor.name,
        action="config_applied" if err is None else "config_apply_failed",
        target=node.name,
        details={"error": err} if err else {},
        ip=actor.ip,
    )
    db.commit()
    return {"ok": err is None, "error": err}


@router.post("/{node_id}/overwrite")
def overwrite(
    node_id: int, request: Request, db: DB, actor: CurrentActor, settings: AppSettings
) -> dict[str, Any]:
    """Abweichung verwerfen: der Node bekommt wieder den Stand des Controllers."""
    node = _get(db, node_id)
    if not node.joined:
        raise HTTPException(status.HTTP_409_CONFLICT, "Der Node ist noch nicht beigetreten")
    node.accepted_hash = None
    if node.is_agent:
        node.force_seq += 1
        err = apply_node(db, node, settings)
    else:
        err = apply_node(db, node, settings, request.app.state.caddy_transport)
    audit.record(
        db,
        actor=actor.name,
        action="node_drift_overwritten",
        target=node.name,
        details={"error": err} if err else {},
        ip=actor.ip,
    )
    db.commit()
    return {"ok": err is None, "error": err}


@router.post("/{node_id}/accept")
def accept(node_id: int, db: DB, actor: CurrentActor, settings: AppSettings) -> NodeOut:
    """Abweichung hinnehmen: die laufende Config bleibt, bis der Controller die nächste
    Änderung an den Node überträgt."""
    node = _get(db, node_id)
    if not node.drift:
        raise HTTPException(status.HTTP_409_CONFLICT, "Keine Abweichung vorhanden")
    node.accepted_hash = node.running_hash
    node.running_config = None
    node.drift_since = None
    audit.record(db, actor=actor.name, action="node_drift_accepted", target=node.name, ip=actor.ip)
    db.commit()
    return _out(db, node, settings)
