"""add trip_plans table

Revision ID: 87d9a1a52cca
Revises: d5e6f7a8b9c0
Create Date: 2026-10-28 10:18:42.659615

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "87d9a1a52cca"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trip_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_driver_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_by_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("base_route_id", sa.Uuid(), nullable=False),
        sa.Column("optimization_run_id", sa.Uuid(), nullable=False),
        sa.Column("refined_route_id", sa.Uuid(), nullable=True),
        sa.Column("refined_provider", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stops_snapshot", sa.JSON(), nullable=False),
        sa.Column("base_distance_meters", sa.BigInteger(), nullable=False),
        sa.Column("base_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("refined_distance_meters", sa.BigInteger(), nullable=True),
        sa.Column("refined_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("refine_error", sa.String(length=512), nullable=True),
        sa.Column("share_token", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["assigned_driver_id"], ["user.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["base_route_id"], ["route_calculations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["optimization_run_id"], ["fuel_optimization_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["refined_route_id"], ["route_calculations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_trip_plans_assigned_driver_id"),
        "trip_plans",
        ["assigned_driver_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trip_plans_base_route_id"),
        "trip_plans",
        ["base_route_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trip_plans_optimization_run_id"),
        "trip_plans",
        ["optimization_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trip_plans_owner_id"), "trip_plans", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_trip_plans_refined_route_id"),
        "trip_plans",
        ["refined_route_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_trip_plans_share_token"), "trip_plans", ["share_token"], unique=True
    )
    op.create_index(
        op.f("ix_trip_plans_status"), "trip_plans", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_trip_plans_vehicle_id"), "trip_plans", ["vehicle_id"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_trip_plans_vehicle_id"), table_name="trip_plans")
    op.drop_index(op.f("ix_trip_plans_status"), table_name="trip_plans")
    op.drop_index(op.f("ix_trip_plans_share_token"), table_name="trip_plans")
    op.drop_index(op.f("ix_trip_plans_refined_route_id"), table_name="trip_plans")
    op.drop_index(op.f("ix_trip_plans_owner_id"), table_name="trip_plans")
    op.drop_index(op.f("ix_trip_plans_optimization_run_id"), table_name="trip_plans")
    op.drop_index(op.f("ix_trip_plans_base_route_id"), table_name="trip_plans")
    op.drop_index(op.f("ix_trip_plans_assigned_driver_id"), table_name="trip_plans")
    op.drop_table("trip_plans")
