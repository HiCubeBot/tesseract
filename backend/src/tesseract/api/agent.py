"""Schnittstelle für den Tesseract-Agent (Phase 4).

Ohne Anmeldung erreichbar ist nur der Beitritt (Token bzw. Abhol-Geheimnis). Alles andere
verlangt das Node-Zertifikat (Caddy reicht den Fingerabdruck weiter) **und** das Agent-Token.
"""

import asyncio
import base64
import binascii
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tesseract import audit
from tesseract import nodes as node_svc
from tesseract.autoban import expire_bans
from tesseract.caddy.config import config_hash
from tesseract.db.models import Node, utcnow
from tesseract.deps import DB, AppSettings, client_fingerprint, client_ip
from tesseract.identity import ca_configured
from tesseract.services import apply_all, get_general, node_config

log = logging.getLogger("tesseract.agent")
router = APIRouter(prefix="/agent", tags=["agent"])

# Höchstwartezeit beim Abholen der Config (Long-Polling)
MAX_WAIT = 25.0


# ---------- Beitritt ----------


class JoinIn(BaseModel):
    token: str = Field(max_length=128)
    csr: str = Field(max_length=8000)
    hostname: str = Field(default="", max_length=255)
    agent_version: str = Field(default="", max_length=32)
    admin_listen: str | None = Field(default=None, max_length=255)


class JoinOut(BaseModel):
    node_id: int
    name: str
    secret: str
    key_fingerprint: str


def _throttle(request: Request) -> str:
    ip = client_ip(request) or "?"
    if request.app.state.enroll_throttle.blocked(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Zu viele Versuche – bitte warten")
    return ip


@router.post("/join")
def join(body: JoinIn, request: Request, db: DB) -> JoinOut:
    ip = _throttle(request)
    node = node_svc.node_for_join_token(db, body.token)
    if node is None:
        request.app.state.enroll_throttle.fail(ip)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Beitritts-Token ungültig oder abgelaufen")
    if not ca_configured(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "Die Zertifizierungsstelle fehlt noch")
    try:
        secret = node_svc.register_join(
            node, body.csr, body.hostname, body.admin_listen, body.agent_version
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    audit.record(
        db,
        actor="agent",
        action="node_join_requested",
        target=node.name,
        details={"hostname": node.join_hostname, "key": node.join_key_fp},
        ip=ip,
    )
    db.commit()
    return JoinOut(
        node_id=node.id, name=node.name, secret=secret, key_fingerprint=node.join_key_fp or ""
    )


@router.get("/join/{node_id}")
def join_status(
    node_id: int,
    request: Request,
    response: Response,
    db: DB,
    x_join_secret: Annotated[str, Header()] = "",
) -> dict[str, Any]:
    ip = _throttle(request)
    node = db.get(Node, node_id)
    result = node_svc.pickup(db, node, x_join_secret) if node else "invalid"
    if result == "invalid":
        request.app.state.enroll_throttle.fail(ip)
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Keine Beitrittsanfrage gefunden")
    if result == "rejected":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Beitritt wurde abgelehnt")
    if result == "pending":
        response.status_code = status.HTTP_202_ACCEPTED
        return {"state": "pending"}
    audit.record(db, actor="agent", action="node_joined", target=node.name, ip=ip)
    db.commit()
    return {"state": "approved", **result}


# ---------- Verbundene Agents ----------


def current_node(request: Request, db: DB, authorization: Annotated[str, Header()] = "") -> Node:
    token = authorization.removeprefix("Bearer ").strip()
    node = node_svc.agent_node(db, client_fingerprint(request), token)
    if node is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Agent nicht erkannt")
    return node


AgentNode = Annotated[Node, Depends(current_node)]


def _desired(db: Session, node: Node, settings) -> tuple[str, dict[str, Any]]:
    config = node_config(db, node, settings)
    digest = config_hash(config)
    if node.desired_hash != digest:
        node.desired_hash = digest
        db.commit()
    return digest, config


@router.get("/config")
async def get_config(
    request: Request,
    node: AgentNode,
    db: DB,
    settings: AppSettings,
    known: str = "",
    force: int = 0,
    wait: Annotated[float, Query(ge=0, le=MAX_WAIT)] = 0,
    tasks: bool = False,
) -> Response:
    """Soll-Config. Kennt der Agent sie schon, wartet die Anfrage bis zu `wait` Sekunden auf
    eine Änderung und endet sonst mit 204 (Long-Polling – funktioniert hinter jedem NAT).
    Agents ab 1.1 (`tasks=1`) bekommen dabei auch Aufgaben – dann ggf. ohne Config."""
    node_id = node.id
    broker = request.app.state.agent_tasks
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait
    first = True
    while True:
        db.expire_all()
        node = db.get(Node, node_id)
        if node is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Agent nicht erkannt")
        # Beim ersten Durchlauf immer frisch berechnen (z. B. abgelaufene Geräte)
        if first or node.desired_hash is None:
            digest, config = await asyncio.to_thread(_desired, db, node, settings)
            first = False
        else:
            digest, config = node.desired_hash, None
        if digest != known or node.force_seq != force:
            if config is None:
                digest, config = await asyncio.to_thread(_desired, db, node, settings)
            body = {"hash": digest, "force": node.force_seq, "config": config}
            if tasks:
                body["tasks"] = broker.take(node_id)
            return Response(json.dumps(body), media_type="application/json")
        if tasks and broker.has(node_id):
            body = {
                "hash": digest,
                "force": node.force_seq,
                "config": None,
                "tasks": broker.take(node_id),
            }
            return Response(json.dumps(body), media_type="application/json")
        if loop.time() >= deadline or await request.is_disconnected():
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        await asyncio.sleep(1.0)


class StatusIn(BaseModel):
    agent_version: str = Field(default="", max_length=32)
    caddy_version: str | None = Field(default=None, max_length=64)
    modules: list[str] | None = Field(default=None, max_length=200)
    admin_listen: str | None = Field(default=None, max_length=255)
    loaded_hash: str | None = Field(default=None, max_length=64)
    load_error: str | None = Field(default=None, max_length=4000)
    running_hash: str | None = Field(default=None, max_length=64)
    # laufende Config als Base64-JSON (nur bei Abweichung) – so stört die WAF der
    # Controller-Domain sich nicht an Coraza-Regeln im Inhalt
    running_config_b64: str | None = Field(default=None, max_length=8_000_000)
    # caddy_*-Metriken des Nodes (Prometheus-Text), wenn der Controller sie haben will
    caddy_metrics: str | None = Field(default=None, max_length=4_000_000)


@router.post("/status")
def post_status(body: StatusIn, request: Request, node: AgentNode, db: DB) -> dict[str, Any]:
    report = body.model_dump(exclude={"running_config_b64", "caddy_metrics"})
    if body.running_config_b64:
        try:
            report["running_config"] = json.loads(base64.b64decode(body.running_config_b64))
        except (binascii.Error, ValueError) as e:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "running_config_b64 ungültig"
            ) from e
    node_svc.record_status(db, node, report)
    db.commit()
    g = get_general(db)
    want = bool(g["metrics_enabled"] and g["metrics_caddy"])
    if want and body.caddy_metrics:
        request.app.state.logs.metrics.set_caddy(node.name, body.caddy_metrics)
    return {"ok": True, "heartbeat": node_svc.HEARTBEAT_SECONDS, "caddy_metrics": want}


class TaskResult(BaseModel):
    result: dict[str, Any]


@router.post("/tasks/{task_id}")
async def task_result(
    task_id: str, body: TaskResult, request: Request, node: AgentNode
) -> dict[str, Any]:
    """Ergebnis einer Aufgabe (siehe tesseract.agent_tasks). Unbekannte oder zu spät
    gelieferte Ergebnisse werden ignoriert."""
    return {"ok": request.app.state.agent_tasks.resolve(task_id, body.result)}


class RenewIn(BaseModel):
    csr: str = Field(max_length=8000)


@router.post("/renew")
def renew(body: RenewIn, request: Request, node: AgentNode, db: DB) -> dict[str, Any]:
    """Neues Node-Zertifikat vor Ablauf (der Agent fragt ab 60 Tage vorher selbst)."""
    try:
        out = node_svc.renew_cert(db, request.app.state.secretbox, node, body.csr)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    audit.record(
        db,
        actor="agent",
        action="node_cert_renewed",
        target=node.name,
        details={"not_after": out["not_after"]},
        ip=client_ip(request),
    )
    db.commit()
    return out


class LogsIn(BaseModel):
    # Zeilen aus Caddys Zugriffs- und WAF-Log (JSON), vom Agent gepuffert und nachgeliefert
    access: list[str] = Field(default_factory=list, max_length=5000)
    waf: list[str] = Field(default_factory=list, max_length=5000)


class WafIn(BaseModel):
    lines: list[str] = Field(max_length=5000)


async def _ingest(
    request: Request, node: Node, db: Session, settings, access: list[str], waf: list[str]
) -> dict[str, Any]:
    violations = request.app.state.logs.node(db, node, access, waf)
    node.last_seen_at = utcnow()
    changed = request.app.state.autoban.feed(db, violations) + expire_bans(db)
    db.commit()
    if changed:
        await asyncio.to_thread(apply_all, db, settings, request.app.state.caddy_transport)
        db.commit()
    return {
        "accepted": len(violations),
        "entries": len(access),
        "banned": [b.ip for b in changed if not b.lifted_at],
    }


@router.post("/logs")
async def post_logs(
    body: LogsIn, request: Request, node: AgentNode, db: DB, settings: AppSettings
) -> dict[str, Any]:
    """Logs eines Nodes: landen in der zentralen Log-Ansicht, WAF-Treffer zählen für die
    Auto-Sperre wie die des lokalen Caddy."""
    return await _ingest(request, node, db, settings, body.access, body.waf)


@router.post("/waf")
async def post_waf(
    body: WafIn, request: Request, node: AgentNode, db: DB, settings: AppSettings
) -> dict[str, Any]:
    """Nur WAF-Zeilen (Agent 0.1)."""
    return await _ingest(request, node, db, settings, [], body.lines)
