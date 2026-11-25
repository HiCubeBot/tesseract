"""Docker-Labels: Proxy-Hosts automatisch aus Container-Labels anlegen und pflegen.

```yaml
labels:
  tesseract.domain: "musik.beispiel.de"   # Pflicht
  tesseract.port: "4533"                  # Pflicht, außer der Container hat genau einen Port
  tesseract.scheme: "http"                # http | https
  tesseract.upstream: "navidrome"         # Ziel-Adresse, Standard: Name des Containers
  tesseract.access: "mtls"                # public | mtls
  tesseract.internal: "true"              # nur aus internen Netzen
  tesseract.grants: "Familie, Ben"        # vorhandene Gruppen/Personen
  tesseract.waf: "block"                  # off | detect | block
  tesseract.tls: "dns"                    # http | dns
  tesseract.robots: "deny-ai"             # off | allow | deny | deny-ai (robots.txt)
  tesseract.enable: "false"               # Container überspringen
```

Woher die Labels kommen: den lokalen Node liest der Controller über `TESSERACT_DOCKER_HOST`
(am besten ein Socket-Proxy mit Nur-Lese-Rechten), Agent-Nodes schicken die Labels ihrer
Container im Status mit (beim Agent ebenfalls `TESSERACT_DOCKER_HOST`).

Regeln:
- Neue Hosts aus Labels sind **Entwürfe**, bis ein Admin sie überträgt – außer
  „direkt übertragen“ ist eingeschaltet. Freigaben gehen nur an Gruppen/Personen, die es
  schon gibt; Labels legen nie Gruppen oder Personen an.
- Vorrang: Ändern sich die Labels, gelten sie (neue Version, Akteur „docker“). Änderungen in der
  Oberfläche bleiben, solange sich die Labels nicht ändern; Felder ohne Label gehören immer
  der Oberfläche.
- Gestoppte oder entfernte Container: Host wird deaktiviert, nicht gelöscht. Läuft der
  Container wieder, wird er wieder aktiviert (nur wenn ihn die Docker-Anbindung abgeschaltet
  hat).
- Eine Domain, die schon ein manuell angelegter Host nutzt, wird nicht übernommen.
"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.db.models import Group, Host, Node, Person

log = logging.getLogger("tesseract.docker")

PREFIX = "tesseract."
ACTOR = "docker"
TRUE = ("1", "true", "yes", "ja", "on")
FALSE = ("0", "false", "no", "nein", "off")


class LabelError(ValueError):
    pass


# ---------- Docker-API ----------


def _client(docker_host: str, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    if transport is not None:
        return httpx.Client(transport=transport, base_url="http://docker", timeout=10.0)
    if docker_host.startswith("unix://"):
        return httpx.Client(
            transport=httpx.HTTPTransport(uds=docker_host.removeprefix("unix://")),
            base_url="http://docker",
            timeout=10.0,
        )
    url = docker_host.replace("tcp://", "http://", 1)
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return httpx.Client(base_url=url.rstrip("/"), timeout=10.0)


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Container aus der Docker-API → nur was Tesseract braucht."""
    labels = {k: str(v) for k, v in (raw.get("Labels") or {}).items() if k.startswith(PREFIX)}
    names = raw.get("Names") or [""]
    ports = sorted({p["PrivatePort"] for p in raw.get("Ports") or [] if p.get("Type") == "tcp"})
    return {
        "id": str(raw.get("Id", ""))[:12],
        "name": names[0].lstrip("/"),
        "state": raw.get("State") or "",
        "labels": labels,
        "ports": ports,
    }


def read_containers(
    docker_host: str, transport: httpx.BaseTransport | None = None
) -> list[dict[str, Any]]:
    """Alle Container (auch gestoppte) mit `tesseract.domain`."""
    filters = json.dumps({"label": ["tesseract.domain"]})
    with _client(docker_host, transport) as c:
        r = c.get("/containers/json", params={"all": "true", "filters": filters})
    r.raise_for_status()
    return [normalize(x) for x in r.json()]


# ---------- Labels auswerten ----------


def _bool(value: str, name: str) -> bool:
    v = value.strip().lower()
    if v in TRUE:
        return True
    if v in FALSE:
        return False
    raise LabelError(f"{name}: true oder false erwartet")


def parse(container: dict[str, Any], groups: dict[str, int], persons: dict[str, int]):
    """Labels → Felder des Hosts (nur die, für die es ein Label gibt). None = überspringen."""
    labels = {k.removeprefix(PREFIX): v.strip() for k, v in container["labels"].items()}
    if "enable" in labels and not _bool(labels["enable"], "tesseract.enable"):
        return None
    domain = labels.get("domain", "")
    if not domain:
        return None
    spec: dict[str, Any] = {"domain": domain}
    port = labels.get("port")
    if port:
        if not port.isdigit() or not 1 <= int(port) <= 65535:
            raise LabelError("tesseract.port: Port 1–65535 erwartet")
        spec["upstream_port"] = int(port)
    elif len(container.get("ports") or []) == 1:
        spec["upstream_port"] = container["ports"][0]
    else:
        raise LabelError("tesseract.port fehlt (der Container hat nicht genau einen Port)")
    spec["upstream_host"] = labels.get("upstream") or container["name"]
    if "scheme" in labels:
        if labels["scheme"] not in ("http", "https"):
            raise LabelError("tesseract.scheme: http oder https")
        spec["upstream_scheme"] = labels["scheme"]
    if "access" in labels:
        if labels["access"] not in ("public", "mtls"):
            raise LabelError("tesseract.access: public oder mtls")
        spec["access"] = labels["access"]
    if "internal" in labels:
        spec["internal"] = _bool(labels["internal"], "tesseract.internal")
    if "waf" in labels:
        if labels["waf"] not in ("off", "detect", "block"):
            raise LabelError("tesseract.waf: off, detect oder block")
        spec["waf_mode"] = labels["waf"]
    if "tls" in labels:
        if labels["tls"] not in ("http", "dns"):
            raise LabelError("tesseract.tls: http oder dns")
        spec["tls_challenge"] = labels["tls"]
    if "robots" in labels:
        mode = labels["robots"].lower().replace("-", "_")
        if mode not in ("off", "allow", "deny", "deny_ai"):
            raise LabelError("tesseract.robots: off, allow, deny oder deny-ai")
        spec["robots"] = mode
    if "grants" in labels:
        gids, pids = [], []
        for name in [n.strip() for n in labels["grants"].split(",") if n.strip()]:
            if name in groups:
                gids.append(groups[name])
            elif name in persons:
                pids.append(persons[name])
            else:
                # Labels dürfen keine Freigaben erfinden – nur Vorhandenes zuordnen
                raise LabelError(f"tesseract.grants: „{name}“ ist keine Gruppe oder Person")
        spec["grant_group_ids"], spec["grant_person_ids"] = gids, pids
    return spec


def spec_hash(spec: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:32]


# ---------- Abgleich ----------


def _input(host: Host) -> dict[str, Any]:
    """Aktueller Stand eines Hosts als Eingabe (für die Prüfungen wie beim Speichern)."""
    from tesseract.api.hosts import HostIn

    simple = set(HostIn.model_fields) - {"paths", "grant_group_ids", "grant_person_ids", "areas"}
    data = {k: getattr(host, k) for k in simple if hasattr(host, k)}
    data["paths"] = [p.path for p in host.paths]
    data["grant_group_ids"] = [g.group_id for g in host.grants if g.group_id]
    data["grant_person_ids"] = [g.person_id for g in host.grants if g.person_id]
    data["areas"] = []  # Bereiche ändern Labels nie
    return data


def _check(db: Session, body, host: Host | None, settings) -> None:
    """Dieselben Prüfungen wie beim Speichern in der Oberfläche. Wirft LabelError."""
    from fastapi import HTTPException

    from tesseract.api import hosts as api

    try:
        api._check_grants(db, body)
        api._ensure_free(db, body.domain, host.id if host else None, settings.controller_domain)
    except HTTPException as e:
        raise LabelError(str(e.detail)) from e


def sync(
    db: Session, node: Node, containers: list[dict[str, Any]], settings, general: dict[str, Any]
) -> dict[str, Any]:
    """Hosts eines Nodes an die Container angleichen. Commit macht diese Funktion selbst
    (pro Host), übertragen (apply) der Aufrufer, wenn `changed` gesetzt ist."""
    from pydantic import ValidationError

    from tesseract import audit
    from tesseract.api.hosts import HostIn
    from tesseract.services import add_version, diff, set_grants, snapshot

    result: dict[str, Any] = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "containers": len(containers),
        "created": [],
        "updated": [],
        "disabled": [],
        "enabled": [],
        "errors": [],
        "changed": False,
    }
    groups = dict(db.execute(select(Group.name, Group.id)).all())
    persons = dict(db.execute(select(Person.name, Person.id)).all())
    mine = {
        h.source_ref: h
        for h in db.scalars(select(Host).where(Host.source == "docker", Host.node_id == node.id))
    }
    seen: set[str] = set()

    for c in containers:
        ref = f"{node.id}:{c['name']}"
        try:
            spec = parse(c, groups, persons)
        except LabelError as e:
            result["errors"].append({"container": c["name"], "error": str(e)})
            if ref in mine:
                seen.add(ref)  # Host behalten, nicht als „Container weg“ deaktivieren
            continue
        if spec is None:
            continue
        seen.add(ref)
        running = c.get("state") == "running"
        host = mine.get(ref)
        digest = spec_hash(spec)
        try:
            if host is None:
                taken = db.scalar(select(Host).where(Host.domain == spec["domain"].lower()))
                if taken is not None:
                    raise LabelError(
                        f"{spec['domain']} gibt es schon als Host – Labels übernehmen keine "
                        "Hosts aus der Oberfläche"
                    )
                body = HostIn(
                    **{
                        "node_id": node.id,
                        "draft": not general.get("docker_auto_activate"),
                        "enabled": running,
                        **spec,
                    }
                )
                _check(db, body, None, settings)
                from tesseract.api.hosts import _assign

                host = Host(version=1)
                _assign(host, body, general)
                host.source, host.source_ref, host.source_hash = "docker", ref, digest
                host.source_disabled = not running
                db.add(host)
                add_version(db, host, actor=ACTOR, comment=f"Aus Docker-Labels ({c['name']})")
                audit.record(
                    db,
                    actor=ACTOR,
                    action="host_created",
                    target=host.domain,
                    details={"container": c["name"], "node": node.name, "draft": host.draft},
                )
                db.commit()
                result["created"].append(host.domain)
                result["changed"] |= not host.draft
                continue

            before = snapshot(host)
            changed_labels = host.source_hash != digest
            if changed_labels:
                data = {**_input(host), **spec}
                body = HostIn(**data)
                _check(db, body, host, settings)
                for k, v in body.model_dump(
                    exclude={"paths", "grant_group_ids", "grant_person_ids", "areas", "comment"}
                ).items():
                    if k in spec and v is not None:
                        setattr(host, k, v)
                if "grant_group_ids" in spec:
                    set_grants(host, body.grant_group_ids, body.grant_person_ids)
                host.source_hash = digest
            # Container gestoppt → abschalten; läuft wieder → einschalten (nur eigenes Abschalten)
            if not running and host.enabled:
                host.enabled, host.source_disabled = False, True
                result["disabled"].append(host.domain)
            elif running and not host.enabled and host.source_disabled:
                host.enabled, host.source_disabled = True, False
                result["enabled"].append(host.domain)
            db.flush()
            db.refresh(host, ["node", "paths", "grants", "areas"])
            changes = diff(before, snapshot(host))
            if not changes:
                db.commit()  # evtl. nur source_hash
                continue
            host.version += 1
            comment = (
                "Docker-Labels geändert"
                if changed_labels
                else ("Container läuft wieder" if host.enabled else "Container gestoppt")
            )
            add_version(db, host, actor=ACTOR, comment=comment)
            audit.record(
                db,
                actor=ACTOR,
                action="host_updated",
                target=host.domain,
                details={"version": host.version, "changes": changes, "container": c["name"]},
            )
            db.commit()
            if changed_labels:
                result["updated"].append(host.domain)
            result["changed"] |= not host.draft
        except (LabelError, ValidationError) as e:
            db.rollback()
            msg = str(e) if isinstance(e, LabelError) else _validation_text(e)
            result["errors"].append({"container": c["name"], "error": msg})

    # Container verschwunden → Host abschalten (nicht löschen)
    for ref, host in mine.items():
        if ref in seen or not host.enabled:
            continue
        before = snapshot(host)
        host.enabled, host.source_disabled = False, True
        db.flush()
        host.version += 1
        add_version(db, host, actor=ACTOR, comment="Container entfernt")
        audit.record(
            db,
            actor=ACTOR,
            action="host_updated",
            target=host.domain,
            details={"version": host.version, "changes": diff(before, snapshot(host))},
        )
        db.commit()
        result["disabled"].append(host.domain)
        result["changed"] |= not host.draft
    return result


def _validation_text(e) -> str:
    try:
        return "; ".join(str(x.get("msg", "")).removeprefix("Value error, ") for x in e.errors())
    except Exception:  # pragma: no cover
        return str(e)


def normalize_report(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Container aus dem Status eines Agents – Werte prüfen, nur tesseract.*-Labels."""
    out = []
    for it in items:
        labels = it.get("labels") if isinstance(it.get("labels"), dict) else {}
        out.append(
            {
                "id": str(it.get("id", ""))[:12],
                "name": str(it.get("name", ""))[:128],
                "state": str(it.get("state", ""))[:32],
                "labels": {
                    str(k)[:64]: str(v)[:500]
                    for k, v in labels.items()
                    if str(k).startswith(PREFIX)
                },
                "ports": [int(p) for p in it.get("ports") or [] if str(p).isdigit()][:50],
            }
        )
    return [c for c in out if c["name"]]


def report_error(app, node: Node, error: str) -> None:
    status = getattr(app.state, "docker_status", None)
    if status is None:
        status = app.state.docker_status = {}
    status[node.name] = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "containers": 0,
        "errors": [{"container": "-", "error": f"Docker: {error}"}],
    }


def run_sync(app, db: Session, node: Node, containers: list[dict[str, Any]]) -> dict[str, Any]:
    """Abgleich + Übertragen + Status merken (für Einstellungen › Integrationen)."""
    from tesseract.services import apply_node, get_general

    general = get_general(db)
    result = sync(db, node, containers, app.state.settings, general)
    if result["changed"]:
        err = apply_node(db, node, app.state.settings, app.state.caddy_transport)
        db.commit()
        if err:
            result["errors"].append({"container": "-", "error": f"Übertragen: {err}"})
    for e in result["errors"]:
        log.warning("Docker-Labels (%s/%s): %s", node.name, e["container"], e["error"])
    status = getattr(app.state, "docker_status", None)
    if status is None:
        status = app.state.docker_status = {}
    status[node.name] = {k: v for k, v in result.items() if k != "changed"}
    return result


async def watch(app, interval: float = 30.0) -> None:
    """Hintergrund: lokalen Docker-Host regelmäßig lesen (nur mit TESSERACT_DOCKER_HOST)."""
    import asyncio

    from tesseract.services import get_general

    settings = app.state.settings
    while True:
        try:
            with app.state.db.sessionmaker() as db:
                if get_general(db)["docker_enabled"] and settings.docker_host:
                    node = db.scalar(select(Node).where(Node.kind == "local").order_by(Node.id))
                    if node is not None:
                        try:
                            containers = await asyncio.to_thread(
                                read_containers,
                                settings.docker_host,
                                getattr(app.state, "docker_transport", None),
                            )
                        except (httpx.HTTPError, ValueError) as e:
                            report_error(app, node, str(e) or e.__class__.__name__)
                        else:
                            await asyncio.to_thread(run_sync, app, db, node, containers)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover – die Schleife darf nie sterben
            log.exception("Docker-Labels: Fehler beim Abgleich")
        await asyncio.sleep(interval)
