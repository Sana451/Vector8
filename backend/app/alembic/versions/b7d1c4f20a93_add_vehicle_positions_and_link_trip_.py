"""Add vehicle positions and link trip plans to shipments

Revision ID: b7d1c4f20a93
Revises: e3e5f88eb5bc
Create Date: 2026-11-05 16:05:00.000000

"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


revision = "b7d1c4f20a93"
down_revision = "e3e5f88eb5bc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vehicle_positions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=512), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_vehicle_positions_vehicle_id", "vehicle_positions", ["vehicle_id"]
    )
    op.create_index(
        "ix_vehicle_positions_recorded_at", "vehicle_positions", ["recorded_at"]
    )
    # Looking up "the newest reading for this vehicle" is the only hot query.
    op.create_index(
        "ix_vehicle_positions_vehicle_recorded",
        "vehicle_positions",
        ["vehicle_id", sa.text("recorded_at DESC")],
    )

    op.add_column("trip_plans", sa.Column("shipment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_trip_plans_shipment_id",
        "trip_plans",
        "shipments",
        ["shipment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_trip_plans_shipment_id", "trip_plans", ["shipment_id"])


def downgrade():
    op.drop_index("ix_trip_plans_shipment_id", table_name="trip_plans")
    op.drop_constraint("fk_trip_plans_shipment_id", "trip_plans", type_="foreignkey")
    op.drop_column("trip_plans", "shipment_id")

    op.drop_index("idx_vehicle_positions_location", table_name="vehicle_positions")
    op.drop_index(
        "ix_vehicle_positions_vehicle_recorded", table_name="vehicle_positions"
    )
    op.drop_index("ix_vehicle_positions_recorded_at", table_name="vehicle_positions")
    op.drop_index("ix_vehicle_positions_vehicle_id", table_name="vehicle_positions")
    op.drop_table("vehicle_positions")
