"""Fachlogik für Hosts, Versionen, Einstellungen und das Übertragen an Nodes."""

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.caddy.client import CaddyClient, CaddyError
from tesseract.caddy.config import AreaSpec, HostSpec, NodeSpec, build_config, config_hash
from tesseract.config import Settings
from tesseract.db.models import (
    Ban,
    CustomCert,
    Device,
    Group,
    Host,
    HostArea,
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
    "tls_challenge",
    "internal",
    "custom_cert",
    "areas",
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
    # Cloudflare-API-Token für DNS-01 – verschlüsselt (secretbox), nie im Klartext ausgeliefert
    "cloudflare_token_enc": "",
    # Auto-Sperre nach WAF-Treffern
    "autoban_enabled": True,
    "autoban_hits": 20,
    "autoban_window_minutes": 10,
    "autoban_hours": 24,
    # nie automatisch sperren (z. B. eigenes Netz)
    "autoban_exempt": ["127.0.0.0/8", "::1/128"],
    # Interne Netze (LAN, VPN) für „Nur intern“: einzelne Netze und IP-Listen
    "internal_networks": [],
    "internal_list_ids": [],
    # Geteilte Wildcard-Zertifikate (DNS-01)
    "wildcard_certs": [],
    # Logs: Aufbewahrung in Tagen (Phase 5)
    "logs_days": 14,
    # Prometheus-Endpunkt /metrics: aus, Schutz "token" | "mtls" | "ip"
    "metrics_enabled": False,
    "metrics_auth": "token",
    "metrics_token_hash": "",
    "metrics_networks": [],
    "metrics_list_ids": [],
    # Caddy-Metriken der Nodes mit ausliefern
    "metrics_caddy": True,
}
CLOUDFLARE_CONTEXT = "cloudflare-token"
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


AREA_FIELDS = (
    "name",
    "paths",
    "access",
    "waf_mode",
    "waf_exclusions",
    "authelia",
    "ip_mode",
    "ip_entries",
)


def _names(db: Session, model, ids: list[int]) -> list[str]:
    if not ids:
        return []
    return sorted(db.scalars(select(model.name).where(model.id.in_(ids))))


def area_snapshot(db: Session, area: HostArea) -> dict[str, Any]:
    data = {f: getattr(area, f) for f in AREA_FIELDS}
    data["grants"] = [
        f"Gruppe {n}" for n in _names(db, Group, area.grant_group_ids or [])
    ] + _names(db, Person, area.grant_person_ids or [])
    data["ip_lists"] = _names(db, IpList, area.ip_list_ids or [])
    return data


def snapshot(host: Host) -> dict[str, Any]:
    special = {"node", "paths", "grants", "ip_lists", "areas", "custom_cert"}
    data = {f: getattr(host, f) for f in SNAPSHOT_FIELDS if f not in special}
    data["node"] = host.node.name
    data["paths"] = [p.path for p in host.paths]
    data["grants"] = grant_labels(host)
    session = Session.object_session(host)
    data["ip_lists"] = ip_list_names(session, list(host.ip_list_ids or [])) if session else []
    data["areas"] = [area_snapshot(session, a) for a in host.areas] if session else []
    cert = session.get(CustomCert, host.custom_cert_id) if session and host.custom_cert_id else None
    data["custom_cert"] = cert.name if cert else None
    return {f: data[f] for f in SNAPSHOT_FIELDS}


def add_version(db: Session, host: Host, *, actor: str, comment: str = "") -> HostVersion:
    db.flush()
    db.refresh(host, ["node", "paths", "grants", "areas"])
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
        elif f == "custom_cert":
            name = snap["custom_cert"]
            cid = db.scalar(select(CustomCert.id).where(CustomCert.name == name)) if name else None
            if name and cid is None:
                missing.append(f"Zertifikat {name}")
            host.custom_cert_id = cid
        elif f == "areas":
            areas = []
            for i, a in enumerate(snap["areas"]):
                groups, persons = [], []
                for label in a.get("grants", []):
                    if label.startswith("Gruppe "):
                        gid = db.scalar(select(Group.id).where(Group.name == label[7:]))
                        groups += [gid] if gid else []
                    else:
                        pid = db.scalar(select(Person.id).where(Person.name == label))
                        persons += [pid] if pid else []
                lists = [
                    lid
                    for n in a.get("ip_lists", [])
                    if (lid := db.scalar(select(IpList.id).where(IpList.name == n)))
                ]
                areas.append(
                    HostArea(
                        position=i,
                        **{k: a.get(k) for k in AREA_FIELDS},
                        grant_group_ids=groups,
                        grant_person_ids=persons,
                        ip_list_ids=lists,
                    )
                )
            host.areas = areas
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
    return persons_for(
        db,
        [g.group_id for g in host.grants if g.group_id is not None],
        [g.person_id for g in host.grants if g.person_id is not None],
    )


def persons_for(db: Session, group_ids: list[int], person_ids_in: list[int]) -> list[Person]:
    person_ids = set(person_ids_in)
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
    areas: list[AreaSpec] | None = None,
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
        tls_challenge=getattr(host, "tls_challenge", "http"),
        areas=tuple(areas or ()),
        internal=bool(getattr(host, "internal", False)),
        custom_cert=getattr(host, "custom_cert_id", None),
    )


def area_specs(db: Session, host: Host) -> list[AreaSpec]:
    out = []
    for a in host.areas:
        allowed = None
        if a.access == "mtls" and (a.grant_group_ids or a.grant_person_ids):
            devices = _active_devices_of(
                db, persons_for(db, a.grant_group_ids or [], a.grant_person_ids or [])
            )
            allowed = tuple((d.fingerprint, d.cert_pem) for d in devices)
        out.append(
            AreaSpec(
                paths=tuple(a.paths or ()),
                access=a.access,
                allowed=allowed,
                waf_mode=a.waf_mode,
                waf_exclusions=tuple(a.waf_exclusions or ()),
                authelia=a.authelia,
                ip_mode=a.ip_mode,
                ip_ranges=tuple(resolve_ranges(db, a.ip_entries or [], a.ip_list_ids or [])),
            )
        )
    return out


def client_ca_der_b64(db: Session) -> tuple[str, ...]:
    """Alle noch gültigen Zwischenzertifikate – das aktive zuerst. Nach einem Wechsel bleibt
    das alte vertraut, bis es abläuft oder kein Gerät mehr davon abhängt."""
    from tesseract import pki
    from tesseract.identity import trusted_intermediates

    return tuple(pki.der_b64(pki.load_cert(a.cert_pem)) for a in trusted_intermediates(db))


def active_bans(db: Session) -> list[str]:
    now = utcnow()
    ips = db.scalars(
        select(Ban.ip).where(Ban.lifted_at.is_(None), Ban.expires_at > now).order_by(Ban.ip)
    )
    return list(dict.fromkeys(ips))


CUSTOM_KEY_CONTEXT = "custom-cert-key"


def custom_cert_material(
    db: Session, settings: Settings, hosts: list[Host]
) -> list[tuple[int, str, str]]:
    """Nur Zertifikate, die von Hosts dieses Nodes genutzt werden (Schlüssel entschlüsselt)."""
    ids = sorted({h.custom_cert_id for h in hosts if h.custom_cert_id})
    if not ids:
        return []
    from tesseract.secretbox import load_secretbox

    box = load_secretbox(settings)
    return [
        (c.id, c.cert_pem, box.decrypt(c.key_enc, CUSTOM_KEY_CONTEXT).decode())
        for c in db.scalars(
            select(CustomCert).where(CustomCert.id.in_(ids)).order_by(CustomCert.id)
        )
    ]


def cloudflare_token(db: Session, settings: Settings) -> str:
    enc = get_general(db)["cloudflare_token_enc"]
    if not enc:
        return ""
    from tesseract.secretbox import load_secretbox

    return load_secretbox(settings).decrypt(enc, CLOUDFLARE_CONTEXT).decode()


def node_config(db: Session, node: Node, settings: Settings) -> dict[str, Any]:
    hosts = db.scalars(
        select(Host).where(Host.node_id == node.id, Host.enabled, Host.draft.is_(False))
    ).all()
    general = get_general(db)
    # Die Route für die Oberfläche gibt es nur auf dem lokalen Node (Controller im selben Netz)
    local = not node.is_agent
    spec = NodeSpec(
        admin_listen=node.admin_listen or settings.caddy_admin_listen,
        hosts=[
            host_spec(
                h,
                allowed=allowed_devices(db, h),
                ip_ranges=resolve_ranges(db, h.ip_entries or [], h.ip_list_ids or []),
                areas=area_specs(db, h),
            )
            for h in hosts
        ],
        controller_domain=settings.controller_domain if local else "",
        controller_upstream=settings.controller_upstream if local else "",
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
        cloudflare_token=cloudflare_token(db, settings),
        banned=tuple(active_bans(db)),
        internal_networks=tuple(
            resolve_ranges(db, general["internal_networks"], general["internal_list_ids"])
        ),
        wildcard_certs=tuple(general["wildcard_certs"]),
        custom_certs=tuple(custom_cert_material(db, settings, hosts)),
        waf_log_file=settings.caddy_waf_log,
        access_log_file=settings.caddy_access_log,
    )
    return build_config(spec)


def apply_node(
    db: Session, node: Node, settings: Settings, transport: httpx.BaseTransport | None = None
) -> str | None:
    """Überträgt die Config an den Node. Gibt eine Fehlermeldung zurück oder None.

    Agent-Nodes holen die Config selbst ab: hier wird nur der Soll-Stand vermerkt."""
    config = node_config(db, node, settings)
    digest = config_hash(config)
    if node.is_agent:
        node.desired_hash = digest
        return None
    try:
        CaddyClient(node.admin_url, transport=transport).load(config)
    except CaddyError as e:
        node.last_apply_error = str(e)
        return str(e)
    node.last_apply_error = None
    node.last_applied_at = node.last_seen_at = utcnow()
    node.applied_hash = node.running_hash = digest
    node.running_config = node.drift_since = node.accepted_hash = None
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
