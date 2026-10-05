"""Add optional AI client usage metadata.

Revision ID: 0004_ai_usage
Revises: 0003_usage_events
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_ai_usage"
down_revision = "0003_usage_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usage_events", sa.Column("model_name", sa.String(120)))
    op.add_column("usage_events", sa.Column("input_tokens", sa.Integer()))
    op.add_column("usage_events", sa.Column("output_tokens", sa.Integer()))


def downgrade() -> None:
    op.drop_column("usage_events", "output_tokens")
    op.drop_column("usage_events", "input_tokens")
    op.drop_column("usage_events", "model_name")
