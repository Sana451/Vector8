"""Add map layer cache tables (traffic, fuel, truck restrictions)

Revision ID: f1b2c3d4e5a6
Revises: migrate_route_calc_tz
Create Date: 2026-09-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


revision = 'f1b2c3d4e5a6'
down_revision = 'migrate_route_calc_tz'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'traffic_snapshots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('request_hash', sa.String(), nullable=False),
        sa.Column('geometry', Geography(geometry_type='LINESTRING', srid=4326), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'request_hash', name='uq_traffic_provider_hash'),
    )
    op.create_index('ix_traffic_snapshots_provider', 'traffic_snapshots', ['provider'])
    op.create_index('ix_traffic_snapshots_request_hash', 'traffic_snapshots', ['request_hash'])
    op.create_index('ix_traffic_snapshots_expires_at', 'traffic_snapshots', ['expires_at'])

    op.create_table(
        'fuel_stations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('brand', sa.String(length=255), nullable=True),
        sa.Column('address', sa.String(length=512), nullable=True),
        sa.Column('location', Geography(geometry_type='POINT', srid=4326), nullable=False),
        sa.Column('diesel_price', sa.Float(), nullable=True),
        sa.Column('truck_accessible', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'external_id', name='uq_fuel_provider_external'),
    )
    op.create_index('ix_fuel_stations_provider', 'fuel_stations', ['provider'])
    op.create_index('ix_fuel_stations_external_id', 'fuel_stations', ['external_id'])
    op.create_index('ix_fuel_stations_expires_at', 'fuel_stations', ['expires_at'])

    op.create_table(
        'truck_restrictions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('restriction_type', sa.String(length=64), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=True),
        sa.Column('location', Geography(geometry_type='POINT', srid=4326), nullable=False),
        sa.Column('max_height_cm', sa.Integer(), nullable=True),
        sa.Column('max_weight_kg', sa.Integer(), nullable=True),
        sa.Column('max_width_cm', sa.Integer(), nullable=True),
        sa.Column('max_length_cm', sa.Integer(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'provider', 'external_id', name='uq_truck_restriction_provider_external'
        ),
    )
    op.create_index('ix_truck_restrictions_provider', 'truck_restrictions', ['provider'])
    op.create_index('ix_truck_restrictions_external_id', 'truck_restrictions', ['external_id'])
    op.create_index('ix_truck_restrictions_expires_at', 'truck_restrictions', ['expires_at'])


def downgrade():
    op.drop_index('ix_truck_restrictions_expires_at', table_name='truck_restrictions')
    op.drop_index('ix_truck_restrictions_external_id', table_name='truck_restrictions')
    op.drop_index('ix_truck_restrictions_provider', table_name='truck_restrictions')
    op.drop_table('truck_restrictions')

    op.drop_index('ix_fuel_stations_expires_at', table_name='fuel_stations')
    op.drop_index('ix_fuel_stations_external_id', table_name='fuel_stations')
    op.drop_index('ix_fuel_stations_provider', table_name='fuel_stations')
    op.drop_table('fuel_stations')

    op.drop_index('ix_traffic_snapshots_expires_at', table_name='traffic_snapshots')
    op.drop_index('ix_traffic_snapshots_request_hash', table_name='traffic_snapshots')
    op.drop_index('ix_traffic_snapshots_provider', table_name='traffic_snapshots')
    op.drop_table('traffic_snapshots')
