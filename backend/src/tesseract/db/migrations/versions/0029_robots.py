"""Hosts: robots.txt direkt von Caddy

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-25 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        b.add_column(sa.Column("robots", sa.String(16), nullable=False, server_default="off"))
        b.add_column(sa.Column("robots_paths", sa.JSON(), nullable=False, server_default="[]"))
        b.add_column(sa.Column("robots_sitemap", sa.String(500), nullable=False, server_default=""))
        b.add_column(sa.Column("robots_text", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        for c in ("robots_text", "robots_sitemap", "robots_paths", "robots"):
            b.drop_column(c)
