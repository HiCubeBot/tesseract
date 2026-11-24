"""Geräte: .p12 und Passwort verschlüsselt aufbewahren

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-24 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as b:
        b.add_column(sa.Column("p12_enc", sa.Text(), nullable=True))
        b.add_column(sa.Column("p12_password_enc", sa.String(255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as b:
        b.drop_column("p12_password_enc")
        b.drop_column("p12_enc")
