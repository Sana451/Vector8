"""Add fleet and fuel optimization tables

Revision ID: 7e3c1d9f0a2b
Revises: 6f2b8c1d4e90
Create Date: 2026-09-24 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "7e3c1d9f0a2b"
down_revision = "6f2b8c1d4e90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vehicle_fuel_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("fuel_type", sa.String(length=64), nullable=False),
        sa.Column("tank_capacity_gallons", sa.Numeric(10, 4), nullable=False),
        sa.Column("usable_tank_capacity_gallons", sa.Numeric(10, 4), nullable=False),
        sa.Column("consumption_mpg", sa.Numeric(8, 3), nullable=False),
        sa.Column("reserve_gallons", sa.Numeric(10, 4), nullable=False),
        sa.Column("min_refuel_gallons", sa.Numeric(10, 4), nullable=True),
        sa.Column("max_refuel_gallons", sa.Numeric(10, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("tank_capacity_gallons > 0", name="ck_vehicle_fuel_profiles_tank_positive"),
        sa.CheckConstraint(
            "usable_tank_capacity_gallons > 0",
            name="ck_vehicle_fuel_profiles_usable_positive",
        ),
        sa.CheckConstraint(
            "usable_tank_capacity_gallons <= tank_capacity_gallons",
            name="ck_vehicle_fuel_profiles_usable_le_tank",
        ),
        sa.CheckConstraint("consumption_mpg > 0", name="ck_vehicle_fuel_profiles_mpg_positive"),
        sa.CheckConstraint("reserve_gallons >= 0", name="ck_vehicle_fuel_profiles_reserve_nonnegative"),
        sa.CheckConstraint(
            "reserve_gallons < usable_tank_capacity_gallons",
            name="ck_vehicle_fuel_profiles_reserve_lt_usable",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "vehicles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("unit_number", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("vehicle_type", sa.String(length=32), nullable=False),
        sa.Column("make", sa.String(length=255), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("routing_profile_id", sa.UUID(), nullable=True),
        sa.Column("fuel_profile_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["fuel_profile_id"], ["vehicle_fuel_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unit_number", name="uq_vehicles_unit_number"),
    )
    op.create_index("ix_vehicles_status", "vehicles", ["status"])
    op.create_index("ix_vehicles_unit_number", "vehicles", ["unit_number"])
    op.create_index("ix_vehicles_fuel_profile_id", "vehicles", ["fuel_profile_id"])
    op.create_index("ix_vehicles_routing_profile_id", "vehicles", ["routing_profile_id"])

    op.create_table(
        "fuel_optimization_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("route_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column("algorithm_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("initial_fuel_gallons", sa.Numeric(10, 4), nullable=False),
        sa.Column("total_fuel_consumed_gallons", sa.Numeric(10, 4), nullable=False),
        sa.Column("total_fuel_purchased_gallons", sa.Numeric(10, 4), nullable=False),
        sa.Column("total_fuel_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_detour_distance_meters", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_detour_time_seconds", sa.Integer(), nullable=False),
        sa.Column("number_of_stops", sa.Integer(), nullable=False),
        sa.Column("remaining_fuel_gallons", sa.Numeric(10, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["route_id"], ["route_calculations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.CheckConstraint("initial_fuel_gallons >= 0", name="ck_fuel_opt_runs_initial_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fuel_optimization_runs_route_id", "fuel_optimization_runs", ["route_id"])
    op.create_index("ix_fuel_optimization_runs_vehicle_id", "fuel_optimization_runs", ["vehicle_id"])

    op.create_table(
        "fuel_optimization_stops",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("optimization_run_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("station_id", sa.UUID(), nullable=False),
        sa.Column("route_offset_meters", sa.Numeric(12, 2), nullable=False),
        sa.Column("fuel_before_gallons", sa.Numeric(10, 4), nullable=False),
        sa.Column("fuel_added_gallons", sa.Numeric(10, 4), nullable=False),
        sa.Column("fuel_after_gallons", sa.Numeric(10, 4), nullable=False),
        sa.Column("fuel_price_per_gallon", sa.Numeric(10, 4), nullable=False),
        sa.Column("fuel_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("detour_distance_meters", sa.Numeric(12, 2), nullable=False),
        sa.Column("detour_time_seconds", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["optimization_run_id"], ["fuel_optimization_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["station_id"], ["fuel_stations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fuel_optimization_stops_optimization_run_id",
        "fuel_optimization_stops",
        ["optimization_run_id"],
    )
    op.create_index(
        "ix_fuel_optimization_stops_station_id",
        "fuel_optimization_stops",
        ["station_id"],
    )


def downgrade():
    op.drop_index("ix_fuel_optimization_stops_station_id", table_name="fuel_optimization_stops")
    op.drop_index(
        "ix_fuel_optimization_stops_optimization_run_id",
        table_name="fuel_optimization_stops",
    )
    op.drop_table("fuel_optimization_stops")

    op.drop_index("ix_fuel_optimization_runs_vehicle_id", table_name="fuel_optimization_runs")
    op.drop_index("ix_fuel_optimization_runs_route_id", table_name="fuel_optimization_runs")
    op.drop_table("fuel_optimization_runs")

    op.drop_index("ix_vehicles_routing_profile_id", table_name="vehicles")
    op.drop_index("ix_vehicles_fuel_profile_id", table_name="vehicles")
    op.drop_index("ix_vehicles_unit_number", table_name="vehicles")
    op.drop_index("ix_vehicles_status", table_name="vehicles")
    op.drop_table("vehicles")

    op.drop_table("vehicle_fuel_profiles")
