"""Add route_calculations table

Revision ID: c7a9b1c2d3e4
Revises: postgis_001
Create Date: 2026-09-18 11:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


revision = 'c7a9b1c2d3e4'
down_revision = 'postgis_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'route_calculations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('request_hash', sa.String(), nullable=False),
        sa.Column('origin', Geography(geometry_type='POINT', srid=4326), nullable=False),
        sa.Column('destination', Geography(geometry_type='POINT', srid=4326), nullable=False),
        sa.Column('geometry', Geography(geometry_type='LINESTRING', srid=4326), nullable=True),
        sa.Column('distance_meters', sa.Integer(), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('request_data', sa.JSON(), nullable=True),
        sa.Column('provider_response', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'request_hash', name='uq_route_calc_provider_hash')
    )


def downgrade():
    op.drop_table('route_calculations')
