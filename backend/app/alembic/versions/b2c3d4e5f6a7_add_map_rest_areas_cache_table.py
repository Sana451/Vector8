"""Add map rest areas cache table

Revision ID: b2c3d4e5f6a7
Revises: f1b2c3d4e5a6
Create Date: 2026-09-21 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


revision = "b2c3d4e5f6a7"
down_revision = "f1b2c3d4e5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "map_rest_areas_cache",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("request_hash", sa.String(), nullable=False),
        sa.Column("route_hash", sa.String(), nullable=False),
        sa.Column("categories_hash", sa.String(), nullable=False),
        sa.Column("corridor_width_meters", sa.Integer(), nullable=False),
        sa.Column("provider_place_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "position",
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        ),
        sa.Column("access", sa.JSON(), nullable=True),
        sa.Column("address", sa.JSON(), nullable=True),
        sa.Column("categories", sa.JSON(), nullable=True),
        sa.Column("distance_meters", sa.Float(), nullable=True),
        sa.Column("result_type", sa.String(length=64), nullable=True),
        sa.Column("ontology_id", sa.String(length=255), nullable=True),
        sa.Column("opening_hours", sa.JSON(), nullable=True),
        sa.Column("contacts", sa.JSON(), nullable=True),
        sa.Column("chains", sa.JSON(), nullable=True),
        sa.Column("references", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "request_hash",
            "provider_place_id",
            name="uq_map_rest_areas_provider_request_place",
        ),
    )
    op.create_index(
        "ix_map_rest_areas_cache_provider",
        "map_rest_areas_cache",
        ["provider"],
    )
    op.create_index(
        "ix_map_rest_areas_cache_request_hash",
        "map_rest_areas_cache",
        ["request_hash"],
    )
    op.create_index(
        "ix_map_rest_areas_cache_route_hash",
        "map_rest_areas_cache",
        ["route_hash"],
    )
    op.create_index(
        "ix_map_rest_areas_cache_categories_hash",
        "map_rest_areas_cache",
        ["categories_hash"],
    )
    op.create_index(
        "ix_map_rest_areas_cache_provider_place_id",
        "map_rest_areas_cache",
        ["provider_place_id"],
    )
    op.create_index(
        "ix_map_rest_areas_cache_expires_at",
        "map_rest_areas_cache",
        ["expires_at"],
    )


def downgrade():
    op.drop_index("ix_map_rest_areas_cache_expires_at", table_name="map_rest_areas_cache")
    op.drop_index(
        "ix_map_rest_areas_cache_provider_place_id",
        table_name="map_rest_areas_cache",
    )
    op.drop_index("ix_map_rest_areas_cache_categories_hash", table_name="map_rest_areas_cache")
    op.drop_index("ix_map_rest_areas_cache_route_hash", table_name="map_rest_areas_cache")
    op.drop_index("ix_map_rest_areas_cache_request_hash", table_name="map_rest_areas_cache")
    op.drop_index("ix_map_rest_areas_cache_provider", table_name="map_rest_areas_cache")
    op.drop_table("map_rest_areas_cache")
