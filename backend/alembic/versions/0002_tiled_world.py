"""Add explicit world bounds and tile-pyramid metadata.

Revision ID: 0002_tiled_world
Revises: 0001_initial
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_tiled_world"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "maps",
        sa.Column(
            "world_bounds",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "maps",
        sa.Column(
            "tile_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.execute(
        """
        UPDATE maps
        SET world_bounds = jsonb_build_object(
                'min_x', 0, 'min_y', 0, 'max_x', 6144, 'max_y', 4096
            ),
            tile_config = jsonb_build_object(
                'url_template', '/map-tiles/{z}/{x}/{y}.webp',
                'tile_size', 256,
                'min_zoom', -4,
                'max_native_zoom', 0,
                'max_zoom', 4
            ),
            coordinate_version = 2,
            default_camera = jsonb_build_object('x', 3072, 'y', 2048, 'z', -3),
            version = version + 1
        """
    )


def downgrade() -> None:
    op.drop_column("maps", "tile_config")
    op.drop_column("maps", "world_bounds")
