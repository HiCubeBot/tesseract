"""Alembic-Umgebung. Wird von tesseract.db.run_migrations mit einer Verbindung aufgerufen."""

from alembic import context

from tesseract.db.models import Base

config = context.config
target_metadata = Base.metadata


def run() -> None:
    connection = config.attributes.get("connection")
    if connection is None:
        from sqlalchemy import create_engine

        connection = create_engine(config.get_main_option("sqlalchemy.url")).connect()
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite kann ALTER TABLE nur eingeschränkt
    )
    with context.begin_transaction():
        context.run_migrations()


run()
