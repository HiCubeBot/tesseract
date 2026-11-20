"""Hosts aus Docker-Labels: Herkunft am Host

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-20 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        b.add_column(sa.Column("source", sa.String(16), nullable=False, server_default="ui"))
        b.add_column(sa.Column("source_ref", sa.String(255), nullable=True))
        b.add_column(sa.Column("source_hash", sa.String(64), nullable=True))
        b.add_column(
            sa.Column("source_disabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        b.drop_column("source_disabled")
        b.drop_column("source_hash")
        b.drop_column("source_ref")
        b.drop_column("source")
