"""Store privacy-limited gateway and app usage counters.

Revision ID: 0003_usage_events
Revises: 0002_tiled_world
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_usage_events"
down_revision = "0002_tiled_world"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("tool_name", sa.String(120)),
        sa.Column("access", sa.String(20), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("client", sa.String(80)),
    )
    op.create_index("ix_usage_events_time_source", "usage_events", ["created_at", "source"])
    op.create_index("ix_usage_events_tool_time", "usage_events", ["tool_name", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_usage_events_tool_time", table_name="usage_events")
    op.drop_index("ix_usage_events_time_source", table_name="usage_events")
    op.drop_table("usage_events")
