"""Move fuel profile fields to vehicles and drop vehicle_fuel_profiles

Revision ID: c4d5e6f7a8b9
Revises: b1c2d3e4f5a6
Create Date: 2026-10-14 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("vehicles", sa.Column("fuel_type", sa.String(length=64), nullable=True))
    op.add_column(
        "vehicles", sa.Column("tank_capacity_gallons", sa.Numeric(10, 4), nullable=True)
    )
    op.add_column(
        "vehicles", sa.Column("consumption_mpg", sa.Numeric(8, 3), nullable=True)
    )

    op.execute(
        """
        UPDATE vehicles
        SET fuel_type = p.fuel_type,
            tank_capacity_gallons = p.tank_capacity_gallons,
            consumption_mpg = p.consumption_mpg
        FROM vehicle_fuel_profiles p
        WHERE p.id = vehicles.fuel_profile_id
        """
    )

    op.alter_column("vehicles", "fuel_type", nullable=False)
    op.alter_column("vehicles", "tank_capacity_gallons", nullable=False)
    op.alter_column("vehicles", "consumption_mpg", nullable=False)

    op.drop_index("ix_vehicles_fuel_profile_id", table_name="vehicles")
    op.drop_column("vehicles", "fuel_profile_id")
    op.drop_table("vehicle_fuel_profiles")


def downgrade():
    op.create_table(
        "vehicle_fuel_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("fuel_type", sa.String(length=64), nullable=False),
        sa.Column("tank_capacity_gallons", sa.Numeric(10, 4), nullable=False),
        sa.Column("consumption_mpg", sa.Numeric(8, 3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tank_capacity_gallons > 0", name="ck_vehicle_fuel_profiles_tank_positive"
        ),
        sa.CheckConstraint(
            "consumption_mpg > 0", name="ck_vehicle_fuel_profiles_mpg_positive"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("vehicles", sa.Column("fuel_profile_id", sa.UUID(), nullable=True))
    op.execute("UPDATE vehicles SET fuel_profile_id = gen_random_uuid()")
    op.execute(
        """
        INSERT INTO vehicle_fuel_profiles
            (id, name, fuel_type, tank_capacity_gallons, consumption_mpg,
             created_at, updated_at)
        SELECT fuel_profile_id, name, fuel_type, tank_capacity_gallons,
               consumption_mpg, created_at, updated_at
        FROM vehicles
        """
    )

    op.alter_column("vehicles", "fuel_profile_id", nullable=False)
    op.create_foreign_key(
        "vehicles_fuel_profile_id_fkey",
        "vehicles",
        "vehicle_fuel_profiles",
        ["fuel_profile_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_vehicles_fuel_profile_id", "vehicles", ["fuel_profile_id"])

    op.drop_column("vehicles", "consumption_mpg")
    op.drop_column("vehicles", "tank_capacity_gallons")
    op.drop_column("vehicles", "fuel_type")
