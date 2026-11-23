"""Nodes: Controller-Adresse des Agents und IP der Verbindung

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-23 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("nodes", schema=None) as b:
        b.add_column(sa.Column("controller_url", sa.String(255), nullable=True))
        b.add_column(sa.Column("agent_ip", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nodes", schema=None) as b:
        b.drop_column("agent_ip")
        b.drop_column("controller_url")
