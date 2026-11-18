"""Phase 4 Agent-Nodes: Beitritt, Identität, Status, Abweichung

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-18 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = [
    sa.Column("kind", sa.String(length=16), nullable=False, server_default="local"),
    sa.Column("admin_listen", sa.String(length=255), nullable=True),
    sa.Column("join_token_hash", sa.String(length=64), nullable=True),
    sa.Column("join_expires_at", sa.DateTime(), nullable=True),
    sa.Column("join_csr", sa.String(), nullable=True),
    sa.Column("join_key_fp", sa.String(length=64), nullable=True),
    sa.Column("join_hostname", sa.String(length=255), nullable=True),
    sa.Column("join_requested_at", sa.DateTime(), nullable=True),
    sa.Column("join_secret_hash", sa.String(length=64), nullable=True),
    sa.Column("join_state", sa.String(length=16), nullable=True),
    sa.Column("cert_pem", sa.String(), nullable=True),
    sa.Column("cert_fingerprint", sa.String(length=64), nullable=True),
    sa.Column("cert_not_after", sa.DateTime(), nullable=True),
    sa.Column("agent_token_hash", sa.String(length=64), nullable=True),
    sa.Column("last_seen_at", sa.DateTime(), nullable=True),
    sa.Column("agent_version", sa.String(length=32), nullable=True),
    sa.Column("caddy_version", sa.String(length=64), nullable=True),
    sa.Column("modules", sa.JSON(), nullable=True),
    sa.Column("desired_hash", sa.String(length=64), nullable=True),
    sa.Column("force_seq", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("running_hash", sa.String(length=64), nullable=True),
    sa.Column("running_config", sa.JSON(), nullable=True),
    sa.Column("drift_since", sa.DateTime(), nullable=True),
    sa.Column("accepted_hash", sa.String(length=64), nullable=True),
]


def upgrade() -> None:
    with op.batch_alter_table("nodes", schema=None) as batch_op:
        for col in COLUMNS:
            batch_op.add_column(col)
        batch_op.create_unique_constraint("uq_nodes_cert_fingerprint", ["cert_fingerprint"])
        batch_op.create_unique_constraint("uq_nodes_join_token_hash", ["join_token_hash"])


def downgrade() -> None:
    with op.batch_alter_table("nodes", schema=None) as batch_op:
        batch_op.drop_constraint("uq_nodes_join_token_hash", type_="unique")
        batch_op.drop_constraint("uq_nodes_cert_fingerprint", type_="unique")
        for col in reversed(COLUMNS):
            batch_op.drop_column(col.name)
