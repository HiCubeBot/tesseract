"""Zertifikatsübersicht (wie bei NPM): welche Zertifikate Caddy ausliefert."""

import asyncio
import base64
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select

from tesseract import pki
from tesseract.caddy.config import covering_wildcard
from tesseract.certs import Probe, explain, issuer_label, parse, probe_all, status, tls_address
from tesseract.db.models import CustomCert, Host, Node
from tesseract.deps import DB, AppSettings, CurrentActor
from tesseract.services import get_general

router = APIRouter(prefix="/certificates", tags=["certificates"])

CACHE_SECONDS = 300


class CertificateOut(BaseModel):
    fingerprint: str
    names: list[str]
    issuer: str
    issuer_raw: str
    not_before: datetime
    not_after: datetime
    days_left: int
    status: Literal["ok", "soon", "expired"]
    # wie es geholt wird
    source: Literal["http-01", "dns-01", "wildcard", "lokal", "eigenes", "unbekannt"]
    hosts: list[str]
    node: str


class ProbeError(BaseModel):
    name: str
    node: str
    error: str


class Overview(BaseModel):
    checked_at: datetime
    certificates: list[CertificateOut]
    errors: list[ProbeError]


def _source(issuer: str, domains: list[str], db_hosts: dict[str, Host], wild: list[str]) -> str:
    if issuer == "Caddy (lokal)":
        return "lokal"
    if any(n.startswith("*.") for n in domains) or any(
        covering_wildcard(d, wild) for d in domains if d in db_hosts
    ):
        return "wildcard"
    challenges = {db_hosts[d].tls_challenge for d in domains if d in db_hosts}
    if challenges == {"dns"}:
        return "dns-01"
    if challenges:
        return "http-01"
    return "unbekannt"


@dataclass
class _Plan:
    node_id: int
    node: str
    kind: str
    address: tuple[str, int]
    names: list[str]
    tasks: bool
    state: str


def _plan(db, settings) -> tuple[dict[str, Host], list[str], dict[str, str], list[_Plan]]:
    """Welche Namen bei welchem Node abgefragt werden."""
    from tesseract import nodes as node_svc
    from tesseract.agent_tasks import supports_tasks

    general = get_general(db)
    wild = list(general["wildcard_certs"])
    hosts = {
        h.domain: h for h in db.scalars(select(Host).where(Host.enabled, Host.draft.is_(False)))
    }
    own = {c.fingerprint: c.name for c in db.scalars(select(CustomCert))}
    plans = []
    for node in db.scalars(select(Node).order_by(Node.name)):
        if not node.joined:
            continue
        names = [d for d, h in hosts.items() if h.node_id == node.id]
        if settings.controller_domain and not node.is_agent:
            names.insert(0, settings.controller_domain)
        # Wildcards ohne eigenen Host: mit einem Beispielnamen abfragen (Wildcards holt jeder Node)
        for w in wild:
            if not any(covering_wildcard(n, [w]) for n in names):
                names.append(w.replace("*.", "tesseract-probe.", 1))
        plans.append(
            _Plan(
                node.id,
                node.name,
                node.kind,
                tls_address(node.admin_url, settings.caddy_tls_address),
                names,
                supports_tasks(node),
                node_svc.state(node),
            )
        )
    return hosts, wild, own, plans


async def _probe_node(request: Request, plan: _Plan) -> tuple[list[Probe], str | None]:
    """Lokaler Node: direkt per TLS. Agent-Node: der Agent fragt seinen Caddy (ab 1.1)."""
    if not plan.names:
        return [], None
    if plan.kind != "agent":
        return await asyncio.to_thread(probe_all, *plan.address, plan.names), None
    if plan.state == "offline":
        return [], "Node ist offline"
    if not plan.tasks:
        return [], "Agent älter als 1.1 – für die Übersicht den Agent aktualisieren"
    r = await request.app.state.agent_tasks.run(
        plan.node_id, "certs", {"names": plan.names}, timeout=20
    )
    if r is None:
        return [], "Node hat nicht geantwortet"
    probes = []
    for name in plan.names:
        item = (r.get("certs") or {}).get(name) or {"error": "keine Antwort"}
        if item.get("der"):
            try:
                probes.append(Probe(name, cert=parse(base64.b64decode(item["der"]))))
                continue
            except ValueError:
                item = {"error": "ungültiges Zertifikat"}
        probes.append(Probe(name, error=str(item.get("error"))))
    return probes, None


def _build(hosts, wild, own, results: list[tuple[_Plan, list[Probe], str | None]]) -> Overview:
    from tesseract.db.models import utcnow

    certificates: dict[str, CertificateOut] = {}
    errors: list[ProbeError] = []
    for plan, probes, problem in results:
        if problem:
            errors.append(ProbeError(name="(alle Namen)", node=plan.node, error=problem))
        for p in probes:
            if p.cert is None:
                errors.append(
                    ProbeError(name=p.name, node=plan.node, error=explain(p.error or "?"))
                )
                continue
            c = p.cert
            label = f"Eigenes · {own[c.fingerprint]}" if c.fingerprint in own else issuer_label(c)
            entry = certificates.get(c.fingerprint)
            host_name = p.name if not p.name.startswith("tesseract-probe.") else None
            if entry is None:
                entry = CertificateOut(
                    fingerprint=pki.format_fingerprint(c.fingerprint),
                    names=c.names,
                    issuer=label,
                    issuer_raw=f"{c.issuer_org} · {c.issuer}".strip(" ·"),
                    not_before=c.not_before,
                    not_after=c.not_after,
                    days_left=max(0, (c.not_after - utcnow()).days),
                    status=status(c),  # type: ignore[arg-type]
                    source="unbekannt",
                    hosts=[],
                    node=plan.node,
                )
                certificates[c.fingerprint] = entry
            elif plan.node not in entry.node.split(", "):
                entry.node += f", {plan.node}"
            if host_name and host_name not in entry.hosts:
                entry.hosts.append(host_name)
    for entry in certificates.values():
        if entry.issuer.startswith("Eigenes"):
            entry.source = "eigenes"
            continue
        entry.source = _source(entry.issuer, [*entry.names, *entry.hosts], hosts, wild)  # type: ignore[assignment]
    ordered = sorted(certificates.values(), key=lambda c: c.not_after)
    return Overview(checked_at=utcnow(), certificates=ordered, errors=errors)


@router.get("")
async def overview(
    request: Request, db: DB, _: CurrentActor, settings: AppSettings, refresh: bool = False
) -> Overview:
    """Ergebnis wird 5 Minuten zwischengespeichert (`refresh=true` erzwingt neu)."""
    cache = getattr(request.app.state, "cert_cache", None)
    if cache and not refresh and time.monotonic() - cache[0] < CACHE_SECONDS:
        return cache[1]
    hosts, wild, own, plans = await asyncio.to_thread(_plan, db, settings)
    probed = await asyncio.gather(*(_probe_node(request, p) for p in plans))
    result = _build(
        hosts, wild, own, [(p, probes, err) for p, (probes, err) in zip(plans, probed, strict=True)]
    )
    request.app.state.cert_cache = (time.monotonic(), result)
    return result
