"""Add geocoding cache table

Revision ID: a7b8c9d0e1f2
Revises: f1b2c3d4e5a6
Create Date: 2026-09-20 11:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


revision = "a7b8c9d0e1f2"
down_revision = "f1b2c3d4e5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "geocoding_cache",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("query_hash", sa.String(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("formatted_address", sa.Text(), nullable=False),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("provider_response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "query_hash", name="uq_geocoding_provider_hash"),
    )
    op.create_index("ix_geocoding_cache_provider", "geocoding_cache", ["provider"])
    op.create_index("ix_geocoding_cache_query_hash", "geocoding_cache", ["query_hash"])
    op.create_index("ix_geocoding_cache_expires_at", "geocoding_cache", ["expires_at"])
    op.execute(
        "CREATE INDEX ix_geocoding_cache_location_gist ON geocoding_cache USING GIST (location)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_geocoding_cache_location_gist")
    op.drop_index("ix_geocoding_cache_expires_at", table_name="geocoding_cache")
    op.drop_index("ix_geocoding_cache_query_hash", table_name="geocoding_cache")
    op.drop_index("ix_geocoding_cache_provider", table_name="geocoding_cache")
    op.drop_table("geocoding_cache")
