"""Phase 4: Nodes mit Agent – Beitritt, Identität, Status, Abweichung, Modul-Erkennung.

Ablauf eines Beitritts:
1. Admin legt den Node an → einmaliges Beitritts-Token (30 Min.).
2. Agent erzeugt seinen Schlüssel und schickt Token + CSR (`POST /api/agent/join`).
   Antwort: ein Geheimnis zum Abholen des Zertifikats.
3. Admin vergleicht den Schlüssel-Fingerabdruck (zeigt auch der Agent an) und bestätigt.
   Der Controller signiert die CSR mit dem Zwischenzertifikat.
4. Agent holt Zertifikat + Agent-Token genau einmal ab und verbindet sich ab dann per mTLS.
"""

import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract import audit, pki
from tesseract.caddy.client import CaddyClient, CaddyError
from tesseract.caddy.config import config_hash
from tesseract.db.models import Node, utcnow
from tesseract.identity import chain, intermediate_keypair
from tesseract.secretbox import SecretBox

log = logging.getLogger("tesseract.nodes")

JOIN_MINUTES = 30
NODE_CERT_DAYS = 730
# Agent meldet sich alle 30 s – nach 90 s ohne Kontakt gilt der Node als offline
HEARTBEAT_SECONDS = 30
OFFLINE_AFTER = timedelta(seconds=90)
NAME_RE = re.compile(r"[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?")

# Modul-Erkennung über Caddys /adapt: der Caddyfile-Adapter scheitert, wenn ein Modul fehlt.
# Nichts davon wird geladen – die laufende Config bleibt unberührt.
MODULE_PROBES: dict[str, str] = {
    "http.handlers.waf": "{\n\torder coraza_waf first\n}\n:1 {\n\tcoraza_waf\n}\n",
    "dns.providers.cloudflare": ":1 {\n\ttls {\n\t\tdns cloudflare probe\n\t}\n}\n",
}


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def normalize_name(name: str) -> str:
    name = name.strip().lower()
    if not NAME_RE.fullmatch(name):
        raise ValueError("Name: nur a–z, 0–9 und Bindestrich, höchstens 64 Zeichen")
    return name


# ---------- Beitritt ----------


def new_join_token(node: Node) -> str:
    """Erzeugt ein neues Beitritts-Token; eine offene Anfrage verfällt damit."""
    token = secrets.token_urlsafe(24)
    node.join_token_hash = _sha(token)
    node.join_expires_at = utcnow() + timedelta(minutes=JOIN_MINUTES)
    node.join_state = None
    node.join_csr = node.join_key_fp = node.join_hostname = node.join_secret_hash = None
    node.join_requested_at = None
    return token


def node_for_join_token(db: Session, token: str) -> Node | None:
    if not token:
        return None
    node = db.scalar(select(Node).where(Node.join_token_hash == _sha(token.strip())))
    if node is None or not node.is_agent:
        return None
    if node.join_expires_at is None or node.join_expires_at <= utcnow():
        return None
    return node


def register_join(
    node: Node, csr_pem: str, hostname: str, admin_listen: str | None, agent_version: str
) -> str:
    """Nimmt die Anfrage des Agents an (Token ist danach verbraucht). Gibt das Abhol-Geheimnis
    zurück. Löst ValueError bei ungültiger CSR aus."""
    csr = pki.load_csr(csr_pem)
    secret = secrets.token_urlsafe(32)
    node.join_token_hash = None
    node.join_expires_at = None
    node.join_csr = csr_pem
    node.join_key_fp = pki.public_key_fingerprint(csr.public_key())
    node.join_hostname = hostname.strip()[:255] or None
    node.join_requested_at = utcnow()
    node.join_secret_hash = _sha(secret)
    node.join_state = "pending"
    if admin_listen:
        node.admin_listen = admin_listen.strip()[:255]
    node.agent_version = agent_version[:32] or None
    return secret


def approve_join(db: Session, box: SecretBox, node: Node) -> None:
    """Signiert die CSR. Ein vorheriges Zertifikat des Nodes gilt damit nicht mehr."""
    if node.join_state != "pending" or not node.join_csr:
        raise ValueError("Keine offene Beitrittsanfrage")
    csr = pki.load_csr(node.join_csr)
    issuer = intermediate_keypair(db, box)
    cert = pki.sign_client(
        issuer,
        csr.public_key(),
        cn=f"node:{node.name}",
        org_unit="Node",
        not_after=utcnow() + timedelta(days=NODE_CERT_DAYS),
    )
    node.cert_pem = pki.cert_pem(cert)
    node.cert_fingerprint = pki.fingerprint(cert)
    node.cert_not_after = cert.not_valid_after_utc
    node.agent_token_hash = None
    node.join_csr = None
    node.join_state = "approved"
    # neuer Agent → alles neu abholen, alter Stand zählt nicht
    node.applied_hash = node.running_hash = node.accepted_hash = None
    node.running_config = None
    node.drift_since = None


def renew_cert(db: Session, box: SecretBox, node: Node, csr_pem: str) -> dict[str, str]:
    """Verbundener Agent holt sich vor Ablauf ein neues Zertifikat (neuer Schlüssel).
    Ab sofort gilt nur noch das neue; das Agent-Token bleibt."""
    csr = pki.load_csr(csr_pem)
    issuer = intermediate_keypair(db, box)
    cert = pki.sign_client(
        issuer,
        csr.public_key(),
        cn=f"node:{node.name}",
        org_unit="Node",
        not_after=utcnow() + timedelta(days=NODE_CERT_DAYS),
    )
    node.cert_pem = pki.cert_pem(cert)
    node.cert_fingerprint = pki.fingerprint(cert)
    node.cert_not_after = cert.not_valid_after_utc
    return {
        "cert_pem": node.cert_pem,
        "chain_pem": "".join(pki.cert_pem(c) for c in chain(db)),
        "not_after": cert.not_valid_after_utc.isoformat(),
    }


def reject_join(node: Node) -> None:
    if node.join_state != "pending":
        raise ValueError("Keine offene Beitrittsanfrage")
    node.join_state = "rejected"
    node.join_csr = None


def pickup(db: Session, node: Node, secret: str) -> dict[str, Any] | str:
    """Zertifikat abholen. Gibt die Daten zurück oder den Zustand ("pending", "rejected",
    "invalid"). Das Agent-Token wird nur hier einmal im Klartext ausgegeben."""
    if not secret or node.join_secret_hash is None or node.join_secret_hash != _sha(secret):
        return "invalid"
    if node.join_state != "approved" or not node.cert_pem:
        return node.join_state or "invalid"
    token = secrets.token_urlsafe(32)
    node.agent_token_hash = _sha(token)
    node.join_secret_hash = None
    node.join_state = None
    return {
        "node_id": node.id,
        "name": node.name,
        "cert_pem": node.cert_pem,
        "chain_pem": "".join(pki.cert_pem(c) for c in chain(db)),
        "agent_token": token,
    }


def agent_node(db: Session, fingerprint: str, token: str) -> Node | None:
    """Node zu Client-Zertifikat (Fingerabdruck von Caddy) und Agent-Token."""
    if not fingerprint or not token:
        return None
    node = db.scalar(select(Node).where(Node.cert_fingerprint == fingerprint))
    if node is None or not node.is_agent or node.agent_token_hash is None:
        return None
    if not secrets.compare_digest(node.agent_token_hash, _sha(token)):
        return None
    if node.cert_not_after is not None and node.cert_not_after <= utcnow():
        return None
    return node


# ---------- Status & Abweichung ----------


def state(node: Node, now: datetime | None = None) -> str:
    """pending | online | offline | drift | error"""
    now = now or utcnow()
    if not node.joined:
        return "pending"
    if node.last_seen_at is None or now - node.last_seen_at > OFFLINE_AFTER:
        # Lokaler Node ohne Kontrollschleife (Tests, Hintergrundaufgaben aus): Fehler zählt
        if not node.is_agent and node.last_seen_at is None:
            return "error" if node.last_apply_error else "online"
        return "offline"
    if node.drift:
        return "drift"
    if node.last_apply_error:
        return "error"
    return "online"


def update_running(
    db: Session, node: Node, running_hash: str | None, running: dict[str, Any] | None
) -> None:
    """Merkt sich, was in Caddy läuft, und erkennt Abweichungen."""
    if running_hash is None:
        return
    node.running_hash = running_hash
    if node.drift:
        if running is not None:
            node.running_config = running
        if node.drift_since is None:
            node.drift_since = utcnow()
            audit.record(
                db,
                actor="system",
                action="node_drift_detected",
                target=node.name,
                details={"running_hash": running_hash[:12]},
            )
    else:
        node.running_config = None
        node.drift_since = None


def record_status(db: Session, node: Node, report: dict[str, Any]) -> None:
    """Statusmeldung eines Agents übernehmen."""
    node.last_seen_at = utcnow()
    node.agent_version = (report.get("agent_version") or "")[:32] or node.agent_version
    if report.get("caddy_version") is not None:
        node.caddy_version = str(report["caddy_version"])[:64] or None
    if report.get("modules") is not None:
        node.modules = sorted({str(m) for m in report["modules"]})
    if report.get("controller"):
        node.controller_url = str(report["controller"])[:255]
    listen = report.get("admin_listen")
    if listen and listen != node.admin_listen:
        node.admin_listen = str(listen)[:255]
    loaded = report.get("loaded_hash")
    if loaded:
        if loaded != node.applied_hash:
            node.last_applied_at = utcnow()
        node.applied_hash = loaded
    node.last_apply_error = report.get("load_error") or None
    update_running(db, node, report.get("running_hash"), report.get("running_config"))


def json_diff(before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
    """Unterschiede zweier JSON-Strukturen als Liste von Pfaden."""
    if isinstance(before, dict) and isinstance(after, dict):
        out = []
        for key in sorted(set(before) | set(after), key=str):
            sub = f"{path}.{key}" if path else str(key)
            if key not in before:
                out.append({"path": sub, "before": None, "after": after[key], "kind": "added"})
            elif key not in after:
                out.append({"path": sub, "before": before[key], "after": None, "kind": "removed"})
            else:
                out += json_diff(before[key], after[key], sub)
        return out
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        out = []
        for i, (b, a) in enumerate(zip(before, after, strict=True)):
            out += json_diff(b, a, f"{path}[{i}]")
        return out
    if before == after:
        return []
    return [{"path": path or "(gesamt)", "before": before, "after": after, "kind": "changed"}]


_ROUTE_RE = re.compile(r"^apps\.http\.servers\.([^.]+)\.routes\[(\d+)\]")


def route_host(config: dict[str, Any], path: str) -> str | None:
    """Zu welchem Host gehört ein Pfad wie `apps.http.servers.https.routes[3]…`?"""
    m = _ROUTE_RE.match(path)
    if not m:
        return None
    try:
        route = config["apps"]["http"]["servers"][m.group(1)]["routes"][int(m.group(2))]
        return route["match"][0]["host"][0]
    except (KeyError, IndexError, TypeError):
        return None


# ---------- Lokaler Node: Kontakt, Abweichung, Module ----------


def probe_modules(client: CaddyClient) -> list[str]:
    """Welche der von Tesseract genutzten Module hat dieser Caddy?"""
    return [name for name, caddyfile in MODULE_PROBES.items() if client.adapt_ok(caddyfile)]


def check_local(
    db: Session, node: Node, transport: httpx.BaseTransport | None = None, modules: bool = False
) -> None:
    """Liest die laufende Config des lokalen Caddy (Abweichung) und optional die Module."""
    client = CaddyClient(node.admin_url, transport=transport)
    try:
        running = client.current_config() or {}
        found = probe_modules(client) if modules else None
    except CaddyError as e:
        log.debug("Lokaler Node %s nicht erreichbar: %s", node.name, e)
        return
    node.last_seen_at = utcnow()
    if found is not None:
        node.modules = sorted(found)
    update_running(db, node, config_hash(running), running)


def track_online(db: Session, seen: dict[int, bool]) -> None:
    """Wechsel online ↔ offline als Audit-Eintrag (Grundlage der Benachrichtigungen).
    Der erste Blick auf einen Node legt nur den Ausgangszustand fest."""
    now = utcnow()
    for node in db.scalars(select(Node)):
        if not node.joined or node.last_seen_at is None:
            continue
        online = state(node, now) != "offline"
        before = seen.get(node.id)
        seen[node.id] = online
        if before is None or before == online:
            continue
        audit.record(
            db,
            actor="system",
            action="node_online" if online else "node_offline",
            target=node.name,
            details={"since": node.last_seen_at.isoformat(timespec="seconds")},
        )


async def watch_local(database, settings, transport=None, interval: float = 30.0) -> None:
    """Hintergrund-Aufgabe: lokale Nodes regelmäßig prüfen (Module alle 10 Minuten)."""
    import asyncio

    rounds = 0
    seen: dict[int, bool] = {}
    while True:
        try:
            with database.sessionmaker() as db:
                for node in db.scalars(select(Node).where(Node.kind == "local")):
                    await asyncio.to_thread(check_local, db, node, transport, rounds % 20 == 0)
                track_online(db, seen)
                db.commit()
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover – die Schleife darf nie sterben
            log.exception("Prüfung der lokalen Nodes fehlgeschlagen")
        rounds += 1
        await asyncio.sleep(interval)
