"""Uptime-Monitor und Statusseite

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-23 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        b.add_column(sa.Column("monitor", sa.Boolean(), nullable=False, server_default=sa.true()))
        b.add_column(
            sa.Column("status_public", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        b.add_column(sa.Column("status_name", sa.String(64), nullable=False, server_default=""))
    op.create_table(
        "monitor_state",
        sa.Column("kind", sa.String(8), primary_key=True),
        sa.Column("ref", sa.String(253), primary_key=True),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("since", sa.DateTime(), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
        sa.Column("ms", sa.Float(), nullable=True),
        sa.Column("error", sa.String(255), nullable=True),
    )
    op.create_table(
        "uptime_daily",
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("kind", sa.String(8), primary_key=True),
        sa.Column("ref", sa.String(253), primary_key=True),
        sa.Column("checks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("up", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("down_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outages", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(8), nullable=False, index=True),
        sa.Column("ref", sa.String(253), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("incidents")
    op.drop_table("uptime_daily")
    op.drop_table("monitor_state")
    with op.batch_alter_table("hosts", schema=None) as b:
        for c in ("status_name", "status_public", "monitor"):
            b.drop_column(c)
