"""Vorab-Prüfungen beim Anlegen/Ändern eines Hosts."""

import socket
import time
from dataclasses import asdict, dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from tesseract.caddy.config import is_public_name
from tesseract.db.models import Host

Status = Literal["ok", "warn", "bad", "info"]


@dataclass
class Check:
    key: str
    title: str
    status: Status
    detail: str

    def dict(self) -> dict[str, str]:
        return asdict(self)


def check_domain_free(
    db: Session, domain: str, exclude_id: int | None, controller_domain: str
) -> Check:
    if controller_domain and domain == controller_domain:
        return Check("domain_free", "Domain noch frei", "bad", "Das ist die Domain von Tesseract")
    stmt = select(Host.id).where(Host.domain == domain)
    if exclude_id:
        stmt = stmt.where(Host.id != exclude_id)
    if db.scalar(stmt) is not None:
        return Check(
            "domain_free", "Domain noch frei", "bad", "Ein anderer Host nutzt diese Domain"
        )
    return Check("domain_free", "Domain noch frei", "ok", "Kein anderer Host nutzt diese Domain")


def check_dns(domain: str, public_ips: list[str], node: str = "") -> Check:
    title = "DNS-Eintrag"
    where = f"den Node „{node}“" if node else "den Node"
    try:
        infos = socket.getaddrinfo(domain, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        status: Status = "warn" if is_public_name(domain) else "info"
        return Check("dns", title, status, f"{domain} löst (noch) nicht auf")
    ips = sorted({str(i[4][0]) for i in infos})
    if public_ips:
        if set(ips) & set(public_ips):
            return Check("dns", f"DNS zeigt auf {where}", "ok", f"{domain} → {', '.join(ips)}")
        return Check(
            "dns",
            f"DNS zeigt auf {where}",
            "warn",
            f"{domain} → {', '.join(ips)}, erwartet: {', '.join(public_ips)}",
        )
    return Check(
        "dns",
        title,
        "ok",
        f"{domain} → {', '.join(ips)} (öffentliche IP unter Nodes › Bearbeiten hinterlegen, "
        "um sie zu vergleichen)",
    )


def check_upstream(host: str, port: int, timeout: float = 2.0) -> Check:
    title = "Ziel erreichbar"
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ms = (time.perf_counter() - start) * 1000
    except OSError as e:
        return Check(
            "upstream",
            title,
            "warn",
            f"{host}:{port} vom Controller aus nicht erreichbar ({e.strerror or e})",
        )
    return Check("upstream", title, "ok", f"{host}:{port} antwortet · {ms:.0f} ms")


def check_port80_hint(domain: str) -> Check:
    if not is_public_name(domain):
        return Check(
            "port80",
            "Zertifikat",
            "info",
            "Kein öffentlicher Name – Caddy nutzt ein eigenes, lokales Zertifikat",
        )
    return Check(
        "port80",
        "Port 80 von außen offen?",
        "info",
        "Wird für die Let's-Encrypt-Prüfung (HTTP-01) gebraucht",
    )
