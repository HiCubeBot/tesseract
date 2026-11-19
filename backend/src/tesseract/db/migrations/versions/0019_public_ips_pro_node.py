"""Öffentliche IPs pro Node statt einmal für alle

Bisher gab es nur eine Liste in den allgemeinen Einstellungen – die galt praktisch für den
lokalen Node. Sie wandert an die lokalen Nodes; Agent-Nodes bekommen ihre eigene.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-19 14:00:00
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("nodes", schema=None) as b:
        b.add_column(sa.Column("public_ips", sa.JSON(), nullable=True))
    conn = op.get_bind()
    row = conn.execute(sa.text("SELECT value FROM settings WHERE key = 'general'")).first()
    if row is None:
        return
    value = row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}")
    ips = value.get("public_ips") or []
    if ips:
        conn.execute(
            sa.text("UPDATE nodes SET public_ips = :ips WHERE kind = 'local'"),
            {"ips": json.dumps(ips)},
        )


def downgrade() -> None:
    with op.batch_alter_table("nodes", schema=None) as b:
        b.drop_column("public_ips")
