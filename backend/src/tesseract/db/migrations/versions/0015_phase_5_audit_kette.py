"""Phase 5 Audit-Log: verkettete Prüfsummen, unveränderlich

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-18 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.add_column(sa.Column("prev_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("hash", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_audit_log_hash", ["hash"])
    # Versiegelte Einträge lassen sich weder ändern noch löschen
    op.execute(
        """
        CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
        WHEN OLD.hash IS NOT NULL
        BEGIN SELECT RAISE(ABORT, 'Audit-Log ist unveränderlich'); END
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
        BEGIN SELECT RAISE(ABORT, 'Audit-Log ist unveränderlich'); END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_delete")
    op.execute("DROP TRIGGER IF EXISTS audit_log_no_update")
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.drop_index("ix_audit_log_hash")
        batch_op.drop_column("hash")
        batch_op.drop_column("prev_hash")
