"""Remove min_refuel_gallons and max_refuel_gallons from vehicle_fuel_profiles - moved to optimization constraints

Revision ID: b1c2d3e4f5a6
Revises: 9a7b8c9d0e1f
Create Date: 2026-10-08 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5a6"
down_revision = "9a7b8c9d0e1f"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("vehicle_fuel_profiles", "min_refuel_gallons")
    op.drop_column("vehicle_fuel_profiles", "max_refuel_gallons")


def downgrade():
    op.add_column(
        "vehicle_fuel_profiles",
        sa.Column("min_refuel_gallons", sa.Numeric(10, 4), nullable=True),
    )
    op.add_column(
        "vehicle_fuel_profiles",
        sa.Column("max_refuel_gallons", sa.Numeric(10, 4), nullable=True),
    )
