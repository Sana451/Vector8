"""Remove usable_tank_capacity_gallons as stored column, make it computed from tank_capacity

Revision ID: 8f5e6d7c8b9a
Revises: 7e3c1d9f0a2b
Create Date: 2026-10-06 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "8f5e6d7c8b9a"
down_revision = "7e3c1d9f0a2b"
branch_labels = None
depends_on = None


def upgrade():
    # Drop constraints that reference usable_tank_capacity_gallons
    op.drop_constraint(
        "ck_vehicle_fuel_profiles_reserve_lt_usable",
        "vehicle_fuel_profiles",
        type_="check",
    )
    op.drop_constraint(
        "ck_vehicle_fuel_profiles_usable_le_tank",
        "vehicle_fuel_profiles",
        type_="check",
    )
    op.drop_constraint(
        "ck_vehicle_fuel_profiles_usable_positive",
        "vehicle_fuel_profiles",
        type_="check",
    )

    # Drop the column
    op.drop_column("vehicle_fuel_profiles", "usable_tank_capacity_gallons")


def downgrade():
    # Add the column back
    op.add_column(
        "vehicle_fuel_profiles",
        sa.Column("usable_tank_capacity_gallons", sa.Numeric(10, 4), nullable=False),
    )

    # Recreate constraints
    op.create_check_constraint(
        "ck_vehicle_fuel_profiles_usable_positive",
        "vehicle_fuel_profiles",
        "usable_tank_capacity_gallons > 0",
    )
    op.create_check_constraint(
        "ck_vehicle_fuel_profiles_usable_le_tank",
        "vehicle_fuel_profiles",
        "usable_tank_capacity_gallons <= tank_capacity_gallons",
    )
    op.create_check_constraint(
        "ck_vehicle_fuel_profiles_reserve_lt_usable",
        "vehicle_fuel_profiles",
        "reserve_gallons < usable_tank_capacity_gallons",
    )
