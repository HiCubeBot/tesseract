"""Zertifikatsübersicht (wie bei NPM): welche Zertifikate Caddy ausliefert."""

import asyncio
import time
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select

from tesseract import pki
from tesseract.caddy.config import covering_wildcard
from tesseract.certs import explain, issuer_label, probe_all, status, tls_address
from tesseract.db.models import Host, Node
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
    source: Literal["http-01", "dns-01", "wildcard", "lokal", "unbekannt"]
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


def _collect(db, settings) -> Overview:
    from tesseract.db.models import utcnow

    general = get_general(db)
    wild = list(general["wildcard_certs"])
    hosts = {
        h.domain: h for h in db.scalars(select(Host).where(Host.enabled, Host.draft.is_(False)))
    }
    certificates: dict[str, CertificateOut] = {}
    errors: list[ProbeError] = []
    for node in db.scalars(select(Node).order_by(Node.name)):
        names = [d for d, h in hosts.items() if h.node_id == node.id]
        if settings.controller_domain and node.name == "local":
            names.insert(0, settings.controller_domain)
        # Wildcards ohne eigenen Host: mit einem Beispielnamen abfragen
        for w in wild:
            if not any(covering_wildcard(n, [w]) for n in names):
                names.append(w.replace("*.", "tesseract-probe.", 1))
        address = tls_address(node.admin_url, settings.caddy_tls_address)
        for p in probe_all(*address, names):
            if p.cert is None:
                errors.append(
                    ProbeError(name=p.name, node=node.name, error=explain(p.error or "?"))
                )
                continue
            c = p.cert
            label = issuer_label(c)
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
                    node=node.name,
                )
                certificates[c.fingerprint] = entry
            if host_name and host_name not in entry.hosts:
                entry.hosts.append(host_name)
    for entry in certificates.values():
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
    result = await asyncio.to_thread(_collect, db, settings)
    request.app.state.cert_cache = (time.monotonic(), result)
    return result
