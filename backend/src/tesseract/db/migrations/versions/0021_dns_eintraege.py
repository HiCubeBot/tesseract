"""DNS-Einträge pro Host (Cloudflare)

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-21 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        b.add_column(sa.Column("dns_type", sa.String(16), nullable=True))
        b.add_column(sa.Column("dns_target", sa.String(500), nullable=False, server_default=""))
        b.add_column(
            sa.Column("dns_proxied", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        b.add_column(sa.Column("dns_records", sa.JSON(), nullable=True))
        b.add_column(sa.Column("dns_error", sa.String(1000), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        for c in ("dns_error", "dns_records", "dns_proxied", "dns_target", "dns_type"):
            b.drop_column(c)
