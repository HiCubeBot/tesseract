"""Dauerhafte IP-Sperren: bans.expires_at darf leer sein (= für immer)

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-19 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("bans", schema=None) as b:
        b.alter_column("expires_at", existing_type=sa.DateTime(), nullable=True)


def downgrade() -> None:
    # Dauerhafte Sperren bekommen beim Zurückgehen ein Ablaufdatum weit in der Zukunft
    op.execute("UPDATE bans SET expires_at = '9999-12-31 00:00:00' WHERE expires_at IS NULL")
    with op.batch_alter_table("bans", schema=None) as b:
        b.alter_column("expires_at", existing_type=sa.DateTime(), nullable=False)
