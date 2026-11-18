"""Fachlogik für Hosts, Versionen, Einstellungen und das Übertragen an Nodes."""

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.caddy.client import CaddyClient, CaddyError
from tesseract.caddy.config import HostSpec, NodeSpec, build_config, config_hash
from tesseract.config import Settings
from tesseract.db.models import Host, HostVersion, Node, Setting, utcnow

# Felder, die eine Host-Version ausmachen (Reihenfolge = Anzeige im Verlauf)
SNAPSHOT_FIELDS = (
    "domain",
    "node",
    "upstream_scheme",
    "upstream_host",
    "upstream_port",
    "websockets",
    "force_https",
    "compression",
    "access",
    "enabled",
    "draft",
)

GENERAL_DEFAULTS: dict[str, Any] = {"acme_email": "", "public_ips": []}


# ---------- Einstellungen ----------


def get_general(db: Session) -> dict[str, Any]:
    row = db.get(Setting, "general")
    return {**GENERAL_DEFAULTS, **(row.value if row else {})}


def set_general(db: Session, value: dict[str, Any]) -> dict[str, Any]:
    merged = {**get_general(db), **value}
    row = db.get(Setting, "general")
    if row is None:
        db.add(Setting(key="general", value=merged))
    else:
        row.value = merged
    return merged


# ---------- Versionen ----------


def snapshot(host: Host) -> dict[str, Any]:
    data = {f: getattr(host, f) for f in SNAPSHOT_FIELDS if f != "node"}
    data["node"] = host.node.name
    return {f: data[f] for f in SNAPSHOT_FIELDS}


def add_version(db: Session, host: Host, *, actor: str, comment: str = "") -> HostVersion:
    db.flush()
    db.refresh(host, ["node"])
    version = HostVersion(
        host_id=host.id, version=host.version, snapshot=snapshot(host), actor=actor, comment=comment
    )
    db.add(version)
    return version


def diff(before: dict[str, Any] | None, after: dict[str, Any]) -> list[dict[str, Any]]:
    if before is None:
        return []
    return [
        {"field": f, "before": before.get(f), "after": after.get(f)}
        for f in SNAPSHOT_FIELDS
        if before.get(f) != after.get(f)
    ]


def apply_snapshot(db: Session, host: Host, snap: dict[str, Any]) -> None:
    for f in SNAPSHOT_FIELDS:
        if f == "node":
            node = db.scalar(select(Node).where(Node.name == snap["node"]))
            if node is not None:
                host.node_id = node.id
        elif f in snap:
            setattr(host, f, snap[f])


# ---------- Caddy ----------


def host_spec(host: Host | Any, host_id: int = 0) -> HostSpec:
    return HostSpec(
        id=host_id or getattr(host, "id", 0) or 0,
        domain=host.domain,
        upstream_scheme=host.upstream_scheme,
        upstream_host=host.upstream_host,
        upstream_port=host.upstream_port,
        websockets=host.websockets,
        force_https=host.force_https,
        compression=host.compression,
    )


def node_config(db: Session, node: Node, settings: Settings) -> dict[str, Any]:
    hosts = db.scalars(
        select(Host).where(Host.node_id == node.id, Host.enabled, Host.draft.is_(False))
    ).all()
    general = get_general(db)
    spec = NodeSpec(
        admin_listen=settings.caddy_admin_listen,
        hosts=[host_spec(h) for h in hosts],
        controller_domain=settings.controller_domain,
        controller_upstream=settings.controller_upstream,
        acme_email=general["acme_email"],
    )
    return build_config(spec)


def apply_node(
    db: Session, node: Node, settings: Settings, transport: httpx.BaseTransport | None = None
) -> str | None:
    """Überträgt die Config an den Node. Gibt eine Fehlermeldung zurück oder None."""
    config = node_config(db, node, settings)
    try:
        CaddyClient(node.admin_url, transport=transport).load(config)
    except CaddyError as e:
        node.last_apply_error = str(e)
        return str(e)
    node.last_apply_error = None
    node.last_applied_at = utcnow()
    node.applied_hash = config_hash(config)
    return None


def node_in_sync(db: Session, node: Node, settings: Settings) -> bool:
    return node.applied_hash == config_hash(node_config(db, node, settings))
