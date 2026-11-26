"""WAF: Ausnahmen mit Kommentar, Ablaufdatum und gezielt (Argument/Pfad); Ziel im Log

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-26 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "waf_exceptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "host_id", sa.Integer(), sa.ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("target", sa.String(200), nullable=False, server_default=""),
        sa.Column("path", sa.String(255), nullable=False, server_default=""),
        sa.Column("comment", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_waf_exceptions_host", "waf_exceptions", ["host_id"])
    with op.batch_alter_table("log_entries", schema=None) as b:
        b.add_column(sa.Column("waf_targets", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("log_entries", schema=None) as b:
        b.drop_column("waf_targets")
    op.drop_index("ix_waf_exceptions_host", table_name="waf_exceptions")
    op.drop_table("waf_exceptions")
