"""Phase 5 Logs: Zugriffs-Log aller Nodes

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-18 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "log_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("node_id", sa.Integer(), nullable=False),
        sa.Column("host", sa.String(length=253), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("uri", sa.String(length=2048), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("waf_rules", sa.JSON(), nullable=False),
        sa.Column("waf_msg", sa.String(length=255), nullable=True),
        sa.Column("waf_score", sa.Integer(), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("ts", "node_id", "host", "ip", "device_id", "reason"):
        op.create_index(f"ix_log_entries_{col}", "log_entries", [col])


def downgrade() -> None:
    for col in ("ts", "node_id", "host", "ip", "device_id", "reason"):
        op.drop_index(f"ix_log_entries_{col}", table_name="log_entries")
    op.drop_table("log_entries")
