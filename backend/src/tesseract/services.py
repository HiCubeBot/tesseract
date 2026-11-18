"""Fachlogik für Hosts, Versionen, Einstellungen und das Übertragen an Nodes."""

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.caddy.client import CaddyClient, CaddyError
from tesseract.caddy.config import HostSpec, NodeSpec, build_config, config_hash
from tesseract.config import Settings
from tesseract.db.models import (
    Device,
    Group,
    Host,
    HostGrant,
    HostPath,
    HostVersion,
    IpList,
    Node,
    Person,
    PersonGroup,
    Setting,
    utcnow,
)

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
    "no_cert_action",
    "paths",
    "grants",
    "waf_mode",
    "waf_paranoia",
    "waf_exclusions",
    "ip_mode",
    "ip_entries",
    "ip_lists",
    "authelia",
    "enabled",
    "draft",
)

GENERAL_DEFAULTS: dict[str, Any] = {
    "acme_email": "",
    "public_ips": [],
    "admin_mtls": False,
    # Coraza: Standard für neue Hosts und Schutz der Oberfläche
    "waf_default_mode": "detect",
    "waf_default_paranoia": 1,
    "controller_waf_mode": "off",
    # Vertrauenswürdige Proxys: einzelne Netze und IDs von IP-Listen
    "trusted_proxies": [],
    "trusted_proxy_list_ids": [],
    # Authelia als Middleware für Hosts (kein Login für die Oberfläche)
    "authelia_url": "",
    "authelia_headers": ["Remote-User", "Remote-Groups", "Remote-Email", "Remote-Name"],
}
ADMIN_GROUP = "Admin"


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


def grant_labels(host: Host) -> list[str]:
    labels = []
    for g in host.grants:
        if g.group is not None:
            labels.append(f"Gruppe {g.group.name}")
        elif g.person is not None:
            labels.append(g.person.name)
    return sorted(labels)


def ip_list_names(db: Session, ids: list[int]) -> list[str]:
    if not ids:
        return []
    return sorted(db.scalars(select(IpList.name).where(IpList.id.in_(ids))))


def resolve_ranges(db: Session, entries: list[str], list_ids: list[int]) -> list[str]:
    """Einzelne Einträge + Inhalte der IP-Listen, ohne Dubletten."""
    ranges = list(entries)
    if list_ids:
        for lst in db.scalars(select(IpList).where(IpList.id.in_(list_ids)).order_by(IpList.id)):
            ranges += lst.entries
    return list(dict.fromkeys(ranges))


def snapshot(host: Host) -> dict[str, Any]:
    special = {"node", "paths", "grants", "ip_lists"}
    data = {f: getattr(host, f) for f in SNAPSHOT_FIELDS if f not in special}
    data["node"] = host.node.name
    data["paths"] = [p.path for p in host.paths]
    data["grants"] = grant_labels(host)
    session = Session.object_session(host)
    data["ip_lists"] = ip_list_names(session, list(host.ip_list_ids or [])) if session else []
    return {f: data[f] for f in SNAPSHOT_FIELDS}


def add_version(db: Session, host: Host, *, actor: str, comment: str = "") -> HostVersion:
    db.flush()
    db.refresh(host, ["node", "paths", "grants"])
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


def set_paths(host: Host, paths: list[str]) -> None:
    host.paths = [HostPath(path=p, position=i) for i, p in enumerate(paths)]


def set_grants(host: Host, group_ids: list[int], person_ids: list[int]) -> None:
    host.grants = [HostGrant(group_id=g) for g in dict.fromkeys(group_ids)] + [
        HostGrant(person_id=p) for p in dict.fromkeys(person_ids)
    ]


def apply_snapshot(db: Session, host: Host, snap: dict[str, Any]) -> list[str]:
    """Setzt den Host auf einen alten Stand. Gibt Freigaben zurück, die es nicht mehr gibt."""
    missing: list[str] = []
    for f in SNAPSHOT_FIELDS:
        if f not in snap:
            continue
        if f == "node":
            node = db.scalar(select(Node).where(Node.name == snap["node"]))
            if node is not None:
                host.node_id = node.id
        elif f == "paths":
            set_paths(host, list(snap["paths"]))
        elif f == "ip_lists":
            ids = [
                i
                for name in snap["ip_lists"]
                if (i := db.scalar(select(IpList.id).where(IpList.name == name))) is not None
            ]
            missing += [f"Liste {n}" for n in snap["ip_lists"] if n not in ip_list_names(db, ids)]
            host.ip_list_ids = ids
        elif f == "grants":
            group_ids, person_ids = [], []
            for label in snap["grants"]:
                if label.startswith("Gruppe "):
                    g = db.scalar(select(Group).where(Group.name == label[len("Gruppe ") :]))
                    if g is not None:
                        group_ids.append(g.id)
                        continue
                else:
                    p = db.scalar(select(Person).where(Person.name == label))
                    if p is not None:
                        person_ids.append(p.id)
                        continue
                missing.append(label)
            set_grants(host, group_ids, person_ids)
        else:
            setattr(host, f, snap[f])
    return missing


# ---------- Freigaben ----------


def granted_persons(db: Session, host: Host) -> list[Person]:
    """Alle nicht gesperrten Personen, die direkt oder über eine Gruppe freigegeben sind."""
    group_ids = [g.group_id for g in host.grants if g.group_id is not None]
    person_ids = {g.person_id for g in host.grants if g.person_id is not None}
    if group_ids:
        person_ids |= set(
            db.scalars(select(PersonGroup.person_id).where(PersonGroup.group_id.in_(group_ids)))
        )
    if not person_ids:
        return []
    return list(
        db.scalars(
            select(Person)
            .where(Person.id.in_(person_ids), Person.disabled.is_(False))
            .order_by(Person.name)
        )
    )


def _active_devices_of(db: Session, persons: list[Person]) -> list[Device]:
    if not persons:
        return []
    return list(
        db.scalars(
            select(Device)
            .where(
                Device.person_id.in_([p.id for p in persons]),
                Device.revoked_at.is_(None),
                Device.not_after > utcnow(),
            )
            .order_by(Device.id)
        )
    )


def admin_devices(db: Session) -> list[Device]:
    """Aktive Geräte nicht gesperrter Personen in der Gruppe „Admin“."""
    group = db.scalar(select(Group).where(Group.name == ADMIN_GROUP, Group.builtin))
    if group is None:
        return []
    return _active_devices_of(db, [p for p in group.persons if not p.disabled])


def device_by_fingerprint(db: Session, fingerprint: str) -> Device | None:
    fp = fingerprint.strip().lower().replace(":", "")
    if len(fp) != 64:
        return None
    return db.scalar(select(Device).where(Device.fingerprint == fp))


def allowed_devices(db: Session, host: Host) -> list[Device]:
    persons = granted_persons(db, host)
    if not persons:
        return []
    return list(
        db.scalars(
            select(Device)
            .where(
                Device.person_id.in_([p.id for p in persons]),
                Device.revoked_at.is_(None),
                Device.not_after > utcnow(),
            )
            .order_by(Device.id)
        )
    )


# ---------- Caddy ----------


def host_spec(
    host: Host | Any,
    host_id: int = 0,
    allowed: list[Device] | None = None,
    paths: list[str] | None = None,
    ip_ranges: list[str] | None = None,
) -> HostSpec:
    if paths is None:
        paths = [p.path for p in host.paths] if isinstance(host, Host) else []
    return HostSpec(
        id=host_id or getattr(host, "id", 0) or 0,
        domain=host.domain,
        upstream_scheme=host.upstream_scheme,
        upstream_host=host.upstream_host,
        upstream_port=host.upstream_port,
        websockets=host.websockets,
        force_https=host.force_https,
        compression=host.compression,
        access=getattr(host, "access", "public"),
        no_cert_action=getattr(host, "no_cert_action", "reject"),
        paths=tuple(paths),
        allowed=tuple((d.fingerprint, d.cert_pem) for d in (allowed or [])),
        waf_mode=getattr(host, "waf_mode", "off"),
        waf_paranoia=getattr(host, "waf_paranoia", 1),
        waf_exclusions=tuple(getattr(host, "waf_exclusions", None) or ()),
        ip_mode=getattr(host, "ip_mode", "off"),
        ip_ranges=tuple(ip_ranges or ()),
        authelia=bool(getattr(host, "authelia", False)),
    )


def client_ca_der_b64(db: Session) -> str:
    from tesseract import pki
    from tesseract.identity import active_authority

    inter = active_authority(db, "intermediate")
    return pki.der_b64(pki.load_cert(inter.cert_pem)) if inter else ""


def node_config(db: Session, node: Node, settings: Settings) -> dict[str, Any]:
    hosts = db.scalars(
        select(Host).where(Host.node_id == node.id, Host.enabled, Host.draft.is_(False))
    ).all()
    general = get_general(db)
    spec = NodeSpec(
        admin_listen=settings.caddy_admin_listen,
        hosts=[
            host_spec(
                h,
                allowed=allowed_devices(db, h),
                ip_ranges=resolve_ranges(db, h.ip_entries or [], h.ip_list_ids or []),
            )
            for h in hosts
        ],
        controller_domain=settings.controller_domain,
        controller_upstream=settings.controller_upstream,
        acme_email=general["acme_email"],
        client_ca_der_b64=client_ca_der_b64(db),
        controller_protected=bool(general["admin_mtls"]),
        controller_allowed=tuple((d.fingerprint, d.cert_pem) for d in admin_devices(db)),
        controller_waf_mode=general["controller_waf_mode"],
        trusted_proxies=tuple(
            resolve_ranges(db, general["trusted_proxies"], general["trusted_proxy_list_ids"])
        ),
        authelia_url=general["authelia_url"],
        authelia_headers=tuple(general["authelia_headers"]),
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


def apply_all(
    db: Session, settings: Settings, transport: httpx.BaseTransport | None = None
) -> list[str]:
    """Überträgt an alle Nodes (z. B. nach Sperren eines Geräts). Gibt Fehler zurück."""
    errors = []
    for node in db.scalars(select(Node)):
        err = apply_node(db, node, settings, transport)
        if err:
            errors.append(f"{node.name}: {err}")
    return errors
