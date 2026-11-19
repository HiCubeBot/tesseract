"""LDAP-Abgleich für Personen und Gruppen.

- Personen und Gruppen aus LDAP werden übernommen und regelmäßig abgeglichen (Name, E-Mail,
  Gruppenzugehörigkeit). Freigaben können dann an LDAP-Gruppen hängen.
- Geräte und Zertifikate verwaltet weiter Tesseract.
- Wer in LDAP deaktiviert ist (Filter) oder dort nicht mehr vorkommt, wird gesperrt – samt
  Geräten (Zertifikate widerrufen, optional abschaltbar).
- Schutz vor Fehlkonfiguration: Liefert LDAP keine einzige Person, obwohl schon welche
  verknüpft sind, wird nichts geändert.

Die eingebaute Gruppe „Admin“ und von Hand angelegte Personen/Gruppen bleiben unberührt.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract import audit
from tesseract.db.models import Group, Person, Setting
from tesseract.identity import revoke_device

log = logging.getLogger("tesseract.ldap")

SECRET_CONTEXT = "ldap-bind-password"
DEFAULTS: dict[str, Any] = {
    "enabled": False,
    # ldap://host:389 oder ldaps://host:636
    "url": "",
    "starttls": False,
    "bind_dn": "",
    "bind_password_enc": "",
    "user_base": "",
    "user_filter": "(objectClass=person)",
    "attr_uid": "uid",
    "attr_name": "cn",
    "attr_mail": "mail",
    # optional: zusätzlicher Filter für deaktivierte Konten, z. B.
    #   389ds/FreeIPA: (nsAccountLock=TRUE) · AD: (userAccountControl:1.2.840.113556.1.4.803:=2)
    "disabled_filter": "",
    "group_base": "",
    "group_filter": "(|(objectClass=groupOfNames)(objectClass=groupOfUniqueNames))",
    "attr_group_name": "cn",
    "attr_member": "member",
    "interval_minutes": 60,
    "revoke_devices": True,
    "last": None,
}


class LDAPError(Exception):
    pass


def get_config(db: Session) -> dict[str, Any]:
    row = db.get(Setting, "ldap")
    cfg = json.loads(json.dumps(DEFAULTS))
    cfg.update(row.value if row else {})
    return cfg


def set_config(db: Session, value: dict[str, Any]) -> dict[str, Any]:
    cfg = {**get_config(db), **value}
    row = db.get(Setting, "ldap")
    if row is None:
        db.add(Setting(key="ldap", value=cfg))
    else:
        row.value = cfg
    return cfg


def _norm(dn: str) -> str:
    return ",".join(p.strip() for p in dn.split(",")).lower()


# ---------- Verbindung ----------


def connect(cfg: dict[str, Any], password: str, connection_factory=None):
    """Bind beim Verzeichnis. `connection_factory` ersetzt ldap3.Connection in Tests."""
    import ldap3
    from ldap3.core.exceptions import LDAPException

    if not cfg["url"]:
        raise LDAPError("Adresse des LDAP-Servers fehlt")
    try:
        if connection_factory is not None:
            conn = connection_factory(cfg, password)
        else:
            server = ldap3.Server(cfg["url"], get_info=ldap3.NONE, connect_timeout=10)
            conn = ldap3.Connection(
                server,
                user=cfg["bind_dn"] or None,
                password=password or None,
                receive_timeout=30,
                raise_exceptions=True,
            )
            conn.open()
            if cfg["starttls"] and not cfg["url"].startswith("ldaps://"):
                conn.start_tls()
            conn.bind()
    except LDAPException as e:
        raise LDAPError(f"Verbindung/Anmeldung am LDAP-Server fehlgeschlagen: {e}") from e
    return conn


def _first(entry, attr: str) -> str:
    if not attr:
        return ""
    try:
        v = entry[attr].value
    except (KeyError, IndexError):  # ldap3 wirft bei fehlenden Attributen
        return ""
    if isinstance(v, list):
        v = v[0] if v else ""
    return str(v or "").strip()


def _all(entry, attr: str) -> list[str]:
    try:
        v = entry[attr].values
    except (KeyError, IndexError):
        return []
    return [str(x) for x in v]


@dataclass
class LdapUser:
    dn: str
    uid: str
    name: str
    mail: str
    disabled: bool


@dataclass
class LdapGroup:
    dn: str
    name: str
    members: set[str]


def fetch(cfg: dict[str, Any], conn) -> tuple[list[LdapUser], list[LdapGroup]]:
    from ldap3 import SUBTREE
    from ldap3.core.exceptions import LDAPException

    attrs = [a for a in (cfg["attr_uid"], cfg["attr_name"], cfg["attr_mail"]) if a]
    try:
        conn.search(cfg["user_base"], cfg["user_filter"], SUBTREE, attributes=attrs)
        entries = list(conn.entries)
        disabled: set[str] = set()
        if cfg["disabled_filter"]:
            conn.search(
                cfg["user_base"],
                f"(&{cfg['user_filter']}{cfg['disabled_filter']})",
                SUBTREE,
                attributes=[],
            )
            disabled = {_norm(e.entry_dn) for e in conn.entries}
        groups: list[LdapGroup] = []
        if cfg["group_base"]:
            conn.search(
                cfg["group_base"],
                cfg["group_filter"],
                SUBTREE,
                attributes=[cfg["attr_group_name"], cfg["attr_member"], "uniqueMember"],
            )
            for g in conn.entries:
                members = {_norm(m) for m in _all(g, cfg["attr_member"]) + _all(g, "uniqueMember")}
                groups.append(LdapGroup(g.entry_dn, _first(g, cfg["attr_group_name"]), members))
    except LDAPException as e:
        raise LDAPError(f"Suche im Verzeichnis fehlgeschlagen: {e}") from e
    users = []
    for e in entries:
        dn = e.entry_dn
        uid = _first(e, cfg["attr_uid"]) or dn
        users.append(
            LdapUser(
                dn=dn,
                uid=uid,
                name=(_first(e, cfg["attr_name"]) or uid)[:64],
                mail=_first(e, cfg["attr_mail"])[:255],
                disabled=_norm(dn) in disabled,
            )
        )
    return users, groups


# ---------- Abgleich ----------


@dataclass
class Result:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    disabled: list[str] = field(default_factory=list)
    enabled: list[str] = field(default_factory=list)
    revoked_devices: int = 0
    groups_created: list[str] = field(default_factory=list)
    memberships_changed: int = 0

    @property
    def access_changed(self) -> bool:
        return bool(self.disabled or self.enabled or self.memberships_changed or self.created)

    def summary(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "updated": self.updated,
            "disabled": self.disabled,
            "enabled": self.enabled,
            "revoked_devices": self.revoked_devices,
            "groups_created": self.groups_created,
            "memberships_changed": self.memberships_changed,
        }


def _unique_name(db: Session, model, wanted: str, own_id: int | None = None) -> str:
    name, n = wanted[:64], 2
    while True:
        other = db.scalar(select(model).where(model.name == name))
        if other is None or other.id == own_id:
            return name
        name = f"{wanted[:58]} ({n})"
        n += 1


def apply(
    db: Session, cfg: dict[str, Any], users: list[LdapUser], groups: list[LdapGroup]
) -> Result:
    """Gleicht die Datenbank an LDAP an. Commit macht der Aufrufer."""
    res = Result()
    linked = {p.ldap_dn: p for p in db.scalars(select(Person).where(Person.ldap_dn.is_not(None)))}
    if not users and linked:
        raise LDAPError(
            "LDAP liefert keine Personen, obwohl schon welche verknüpft sind – Filter und "
            "Suchbasis prüfen. Es wurde nichts geändert."
        )
    seen: dict[str, Person] = {}
    for u in users:
        key = _norm(u.dn)
        p = linked.get(key)
        if p is None:
            # gleichnamige, von Hand angelegte Person übernehmen statt doppelt anlegen
            p = db.scalar(select(Person).where(Person.name == u.name, Person.ldap_dn.is_(None)))
            if p is None:
                p = Person(name=_unique_name(db, Person, u.name), ldap_dn=key, email=u.mail or None)
                db.add(p)
                db.flush()
                res.created.append(p.name)
            else:
                p.ldap_dn = key
                res.updated.append(p.name)
        else:
            wanted = _unique_name(db, Person, u.name, p.id)
            if p.name != wanted or (p.email or "") != u.mail:
                p.name, p.email = wanted, u.mail or None
                res.updated.append(p.name)
        if u.disabled and not p.disabled:
            _disable(cfg, p, res, "in LDAP deaktiviert")
        elif not u.disabled and p.disabled:
            p.disabled = False
            res.enabled.append(p.name)
        seen[key] = p
    # In LDAP verschwunden → sperren
    for key, p in linked.items():
        if key not in seen and not p.disabled:
            _disable(cfg, p, res, "nicht mehr in LDAP")

    # Gruppen
    linked_groups = {
        g.ldap_dn: g for g in db.scalars(select(Group).where(Group.ldap_dn.is_not(None)))
    }
    for lg in groups:
        key = _norm(lg.dn)
        g = linked_groups.get(key)
        if g is None:
            g = Group(
                name=_unique_name(db, Group, lg.name or key),
                ldap_dn=key,
                description="aus LDAP",
            )
            db.add(g)
            db.flush()
            res.groups_created.append(g.name)
        if g.builtin:
            continue
        wanted = {seen[m] for m in lg.members if m in seen}
        current = set(g.persons)
        if wanted != current:
            g.persons = sorted(wanted, key=lambda p: p.name)
            res.memberships_changed += len(wanted ^ current)
    return res


def _disable(cfg: dict[str, Any], p: Person, res: Result, reason: str) -> None:
    p.disabled = True
    res.disabled.append(p.name)
    if cfg["revoke_devices"]:
        for d in p.devices:
            if d.revoked_at is None:
                revoke_device(d, reason)
                res.revoked_devices += 1


def run(
    db: Session,
    settings,
    box,
    actor: str = "system",
    dry_run: bool = False,
    transport=None,
    connection_factory=None,
) -> dict[str, Any]:
    """Abgleich ausführen (oder nur anzeigen, was passieren würde)."""
    from tesseract.services import apply_all

    cfg = get_config(db)
    password = (
        box.decrypt(cfg["bind_password_enc"], SECRET_CONTEXT).decode()
        if (cfg["bind_password_enc"])
        else ""
    )
    last: dict[str, Any] = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "ok": False}
    try:
        conn = connect(cfg, password, connection_factory)
        try:
            users, groups = fetch(cfg, conn)
        finally:
            conn.unbind()
        res = apply(db, cfg, users, groups)
        last.update(ok=True, users=len(users), groups=len(groups), **res.summary())
    except LDAPError as e:
        db.rollback()
        last["error"] = str(e)
        if not dry_run:
            set_config(db, {"last": last})
            audit.record(db, actor=actor, action="ldap_sync_failed", details={"error": str(e)})
            db.commit()
        return last
    if dry_run:
        db.rollback()
        return {**last, "dry_run": True}
    set_config(db, {"last": last})
    audit.record(
        db,
        actor=actor,
        action="ldap_synced",
        target=cfg["url"],
        details={k: v for k, v in res.summary().items() if v},
    )
    db.commit()
    if res.access_changed:
        apply_all(db, settings, transport)
        db.commit()
    return last


async def watch(app, interval: float = 60.0) -> None:
    """Hintergrund: im eingestellten Abstand abgleichen."""
    import asyncio

    while True:
        try:
            with app.state.db.sessionmaker() as db:
                cfg = get_config(db)
                last = cfg.get("last") or {}
                due = True
                if last.get("at"):
                    age = datetime.now(UTC) - datetime.fromisoformat(last["at"])
                    due = age.total_seconds() >= max(5, int(cfg["interval_minutes"])) * 60
                if cfg["enabled"] and due:
                    await asyncio.to_thread(
                        run,
                        db,
                        app.state.settings,
                        app.state.secretbox,
                        "system",
                        False,
                        app.state.caddy_transport,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover – die Schleife darf nie sterben
            log.exception("LDAP-Abgleich: Fehler")
        await asyncio.sleep(interval)
