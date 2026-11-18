"""Start des Controllers: Datenbank, Migrationen, erster Admin, lokaler Node."""

import logging

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
