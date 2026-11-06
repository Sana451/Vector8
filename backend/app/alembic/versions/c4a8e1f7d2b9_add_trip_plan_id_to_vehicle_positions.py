"""Link vehicle positions to the trip plan that produced them

Revision ID: c4a8e1f7d2b9
Revises: b7d1c4f20a93
Create Date: 2026-11-06 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c4a8e1f7d2b9"
down_revision = "b7d1c4f20a93"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "vehicle_positions", sa.Column("trip_plan_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_vehicle_positions_trip_plan_id",
        "vehicle_positions",
        "trip_plans",
        ["trip_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_vehicle_positions_trip_plan_id", "vehicle_positions", ["trip_plan_id"]
    )


def downgrade():
    op.drop_index("ix_vehicle_positions_trip_plan_id", table_name="vehicle_positions")
    op.drop_constraint(
        "fk_vehicle_positions_trip_plan_id", "vehicle_positions", type_="foreignkey"
    )
    op.drop_column("vehicle_positions", "trip_plan_id")
