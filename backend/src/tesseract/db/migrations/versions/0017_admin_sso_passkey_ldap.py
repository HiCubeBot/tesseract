"""SSO (OIDC) und Passkeys für Admins, LDAP-Abgleich für Personen und Gruppen

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-19 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("admins", schema=None) as b:
        b.add_column(sa.Column("source", sa.String(16), nullable=False, server_default="local"))
        b.add_column(sa.Column("oidc_subject", sa.String(512), nullable=True))
        b.add_column(sa.Column("email", sa.String(255), nullable=True))
        b.add_column(sa.Column("last_login_at", sa.DateTime(), nullable=True))
        b.create_unique_constraint("uq_admins_oidc_subject", ["oidc_subject"])
    op.create_table(
        "admin_passkeys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("credential_id", sa.String(1024), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False),
        sa.Column("transports", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_id"),
    )
    with op.batch_alter_table("persons", schema=None) as b:
        b.add_column(sa.Column("email", sa.String(255), nullable=True))
        b.add_column(sa.Column("ldap_dn", sa.String(1024), nullable=True))
        b.create_unique_constraint("uq_persons_ldap_dn", ["ldap_dn"])
    with op.batch_alter_table("groups", schema=None) as b:
        b.add_column(sa.Column("ldap_dn", sa.String(1024), nullable=True))
        b.create_unique_constraint("uq_groups_ldap_dn", ["ldap_dn"])


def downgrade() -> None:
    with op.batch_alter_table("groups", schema=None) as b:
        b.drop_constraint("uq_groups_ldap_dn", type_="unique")
        b.drop_column("ldap_dn")
    with op.batch_alter_table("persons", schema=None) as b:
        b.drop_constraint("uq_persons_ldap_dn", type_="unique")
        b.drop_column("ldap_dn")
        b.drop_column("email")
    op.drop_table("admin_passkeys")
    with op.batch_alter_table("admins", schema=None) as b:
        b.drop_constraint("uq_admins_oidc_subject", type_="unique")
        for c in ("last_login_at", "email", "oidc_subject", "source"):
            b.drop_column(c)
