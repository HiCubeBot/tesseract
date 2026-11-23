"""Logs: empfangene Bytes, HTTP-Version und Kompression

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-23 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("log_entries", schema=None) as b:
        b.add_column(sa.Column("bytes_in", sa.Integer(), nullable=False, server_default="0"))
        b.add_column(sa.Column("proto", sa.String(8), nullable=True))
        b.add_column(sa.Column("encoding", sa.String(16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("log_entries", schema=None) as b:
        b.drop_column("encoding")
        b.drop_column("proto")
        b.drop_column("bytes_in")
