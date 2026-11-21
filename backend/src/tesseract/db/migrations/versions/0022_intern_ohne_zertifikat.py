"""mTLS-Hosts: aus internen Netzen ohne Zertifikat

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-22 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        b.add_column(
            sa.Column("internal_no_cert", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        b.drop_column("internal_no_cert")
