"""Hosts: Tesseract selbst (Controller-Zertifikat) darf zugreifen

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-24 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        b.add_column(
            sa.Column("allow_controller", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("hosts", schema=None) as b:
        b.drop_column("allow_controller")
