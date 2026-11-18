"""Installationsskript für weitere Nodes: `curl -fsSL https://<controller>/install/node.sh | sh`.

Das Skript enthält keine Geheimnisse – das Beitritts-Token kommt als Argument dazu. Es ist für
einen Controller immer gleich (Adresse, Version, ggf. CA), deshalb lässt sich seine Prüfsumme
vorab anzeigen und beim Herunterladen vergleichen.
"""

import hashlib
import logging
import time
from importlib import resources
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy import select

from tesseract import __version__
from tesseract.caddy.client import CaddyClient, CaddyError
from tesseract.caddy.config import is_public_name
from tesseract.db.models import Node
from tesseract.deps import DB

log = logging.getLogger("tesseract.install")
router = APIRouter(tags=["install"])
CA_CACHE_SECONDS = 3600


def controller_url(request: Request, settings) -> str:
    if settings.controller_domain:
        return f"https://{settings.controller_domain}"
    return str(request.base_url).rstrip("/")


def _template(name: str) -> str:
    return resources.files("tesseract.install").joinpath(name).read_text(encoding="utf-8")


def controller_ca(request: Request, db) -> str:
    """Root von Caddys eigener CA, wenn die Oberfläche einen internen Namen hat (sonst leer).
    Kommt vom lokalen Caddy (GET /pki/ca/local), 1 Stunde zwischengespeichert."""
    settings = request.app.state.settings
    domain = settings.controller_domain
    if not domain or is_public_name(domain):
        return ""
    cached = getattr(request.app.state, "install_ca", None)
    if cached and time.monotonic() - cached[0] < CA_CACHE_SECONDS:
        return cached[1]
    node = db.scalar(select(Node).where(Node.kind == "local").order_by(Node.id))
    pem = ""
    if node is not None:
        try:
            info = CaddyClient(node.admin_url, transport=request.app.state.caddy_transport).pki()
            pem = (info.get("root_certificate") or "").strip()
        except CaddyError as e:
            log.warning("CA von Caddy nicht lesbar: %s", e)
    request.app.state.install_ca = (time.monotonic(), pem)
    return pem


def render(request: Request, db) -> str:
    settings = request.app.state.settings
    compose = _template("node-compose.yaml").rstrip("\n")
    ca = controller_ca(request, db)
    script = _template("node.sh")
    return (
        script.replace("__CONTROLLER__", controller_url(request, settings))
        .replace("__VERSION__", __version__)
        .replace("__COMPOSE__", compose)
        .replace("__CA_PEM__", ca)
    )


def install_info(request: Request, db, token: str) -> dict[str, Any]:
    """Befehl für die Nodes-Seite. Bei interner Domain mit Prüfsumme statt blindem `-k`."""
    script = render(request, db)
    sha = hashlib.sha256(script.encode()).hexdigest()
    url = controller_url(request, request.app.state.settings) + "/install/node.sh"
    if url.startswith("https://") and not is_public_name(url.split("/")[2].split(":")[0]):
        cmd = (
            f"curl -fsSLk {url} -o tesseract-node.sh && "
            f'echo "{sha}  tesseract-node.sh" | sha256sum -c - && '
            f"sudo sh tesseract-node.sh --token {token}"
        )
    else:
        cmd = f"curl -fsSL {url} | sudo sh -s -- --token {token}"
    return {"command": cmd, "sha256": sha, "url": url}


@router.get("/install/node.sh", include_in_schema=False)
def node_script(request: Request, db: DB) -> Response:
    return Response(render(request, db), media_type="text/x-shellscript; charset=utf-8")
