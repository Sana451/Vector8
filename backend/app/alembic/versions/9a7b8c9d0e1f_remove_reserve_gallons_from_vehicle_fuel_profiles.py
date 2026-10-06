"""Remove reserve_gallons from vehicle_fuel_profiles - moved to optimization constraints

Revision ID: 9a7b8c9d0e1f
Revises: 8f5e6d7c8b9a
Create Date: 2026-10-06 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "9a7b8c9d0e1f"
down_revision = "8f5e6d7c8b9a"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the check constraint for reserve_gallons
    # Note: ck_vehicle_fuel_profiles_reserve_lt_usable was already dropped
    # when usable_tank_capacity_gallons was removed
    op.drop_constraint(
        "ck_vehicle_fuel_profiles_reserve_nonnegative",
        "vehicle_fuel_profiles",
        type_="check",
    )

    # Drop the column
    op.drop_column("vehicle_fuel_profiles", "reserve_gallons")


def downgrade():
    # Add the column back
    op.add_column(
        "vehicle_fuel_profiles",
        sa.Column("reserve_gallons", sa.Numeric(10, 4), nullable=False),
    )

    # Recreate constraint
    op.create_check_constraint(
        "ck_vehicle_fuel_profiles_reserve_nonnegative",
        "vehicle_fuel_profiles",
        "reserve_gallons >= 0",
    )
