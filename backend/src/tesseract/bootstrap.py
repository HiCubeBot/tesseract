"""Start des Controllers: Datenbank, Migrationen, erster Admin, lokaler Node."""

import logging
from typing import Any

from sqlalchemy import select

from tesseract.auth import ensure_admin
from tesseract.config import Settings
from tesseract.db import Database, make_engine, run_migrations
from tesseract.db.models import Node

log = logging.getLogger("tesseract")

LOCAL_NODE = "local"


def init_database(settings: Settings) -> Database:
    engine = make_engine(settings)
    run_migrations(engine)
    database = Database(engine)

    with database.sessionmaker() as db:
        # Phase 1: genau ein Node – der Caddy im selben Compose-Stack
        node = db.scalar(select(Node).where(Node.name == LOCAL_NODE))
        if node is None:
            db.add(Node(name=LOCAL_NODE, location="lokal", admin_url=settings.caddy_admin_url))
        elif node.admin_url != settings.caddy_admin_url:
            node.admin_url = settings.caddy_admin_url
        db.commit()

        password = ensure_admin(db)
        if password:
            log.warning(
                "Erster Start: Admin 'admin' angelegt. Passwort: %s – bitte nach dem Login ändern.",
                password,
            )
    return database


async def sync_nodes_on_start(
    database: Database, settings: Settings, transport: Any = None
) -> None:
    """Überträgt beim Start die Config an alle Nodes. Caddy startet evtl. später –
    daher einige Versuche mit Pause."""
    import asyncio

    from tesseract.services import apply_node

    for attempt in range(10):
        with database.sessionmaker() as db:
            nodes = db.scalars(select(Node)).all()
            errors = [
                err
                for node in nodes
                if (err := await asyncio.to_thread(apply_node, db, node, settings, transport))
            ]
            db.commit()
        if not errors:
            log.info("Config an alle Nodes übertragen")
            return
        if attempt == 9:
            log.error("Config konnte nicht übertragen werden: %s", "; ".join(errors))
            return
        await asyncio.sleep(3)
