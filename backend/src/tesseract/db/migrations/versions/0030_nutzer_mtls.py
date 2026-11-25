"""Personen: Zugriff auf Tesseract per Gerätezertifikat (Rolle)

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-25 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("persons", schema=None) as b:
        b.add_column(sa.Column("ui_role", sa.String(8), nullable=False, server_default="none"))


def downgrade() -> None:
    with op.batch_alter_table("persons", schema=None) as b:
        b.drop_column("ui_role")
