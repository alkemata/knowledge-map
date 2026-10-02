"""Initial knowledge map schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-02
"""
from alembic import op

from app.database import Base
from app import models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The initial migration is generated from the pinned v1 metadata.
    # Later schema changes use explicit additive Alembic operations.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Operators restore a tested backup for an incompatible rollback.
    raise RuntimeError("Initial schema downgrade is destructive; restore a backup instead")
