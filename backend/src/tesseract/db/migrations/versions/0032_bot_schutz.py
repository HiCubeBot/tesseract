"""Hosts: Bot-Schutz mit Anubis (an/aus, nur bestimmte Pfade, Ausnahme-Pfade)

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-26 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        b.add_column(
            sa.Column("bot_protection", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        b.add_column(sa.Column("bot_paths", sa.JSON(), nullable=False, server_default="[]"))
        b.add_column(sa.Column("bot_exempt", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        for c in ("bot_exempt", "bot_paths", "bot_protection"):
            b.drop_column(c)
