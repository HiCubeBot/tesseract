"""Statistik: Stadt/ASN in den Logs, Tages- und Stundenwerte, Besucher-IPs

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-23 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTERS = [
    "requests",
    "denied",
    "mtls",
    "waf",
    "ipfilter",
    "s2xx",
    "s3xx",
    "s4xx",
    "s5xx",
    "bytes_out",
    "bytes_in",
    "http1",
    "http2",
    "http3",
    "browser",
    "app",
    "bot",
    "compressed",
    "compressible",
    "visitors",
]


def upgrade() -> None:
    with op.batch_alter_table("log_entries", schema=None) as b:
        b.add_column(sa.Column("city", sa.String(64), nullable=True))
        b.add_column(sa.Column("lat", sa.Float(), nullable=True))
        b.add_column(sa.Column("lon", sa.Float(), nullable=True))
        b.add_column(sa.Column("asn", sa.Integer(), nullable=True))
        b.add_column(sa.Column("as_org", sa.String(128), nullable=True))
    op.create_table(
        "stats_daily",
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("host", sa.String(253), primary_key=True),
        sa.Column("node", sa.String(64), primary_key=True),
        *(sa.Column(c, sa.Integer(), nullable=False, server_default="0") for c in COUNTERS),
        sa.Column("median_ms", sa.Float(), nullable=True),
        sa.Column("codes", sa.JSON(), nullable=False),
        sa.Column("clients", sa.JSON(), nullable=False),
    )
    op.create_table(
        "stats_hourly",
        sa.Column("hour", sa.DateTime(), primary_key=True),
        sa.Column("requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("denied", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bytes_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("top_host", sa.String(253), nullable=True),
        sa.Column("top_denied_host", sa.String(253), nullable=True),
    )
    op.create_table(
        "visitor_ips",
        sa.Column("ip", sa.String(64), primary_key=True),
        sa.Column("first_day", sa.String(10), nullable=False),
        sa.Column("last_day", sa.String(10), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("visitor_ips")
    op.drop_table("stats_hourly")
    op.drop_table("stats_daily")
    with op.batch_alter_table("log_entries", schema=None) as b:
        for c in ("as_org", "asn", "lon", "lat", "city"):
            b.drop_column(c)
