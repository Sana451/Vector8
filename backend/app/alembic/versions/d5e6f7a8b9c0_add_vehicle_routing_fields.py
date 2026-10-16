"""Add HERE routing fields to vehicles and drop routing_profile_id

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-10-16 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None

INT_COLUMNS = [
    "height_in",
    "width_in",
    "length_in",
    "gross_weight_lbs",
    "weight_per_axle_lbs",
    "axle_count",
    "tires_count",
    "trailer_length_in",
    "kpra_length_in",
    "payload_capacity_lbs",
    "max_speed_mph",
]


def upgrade():
    for name in INT_COLUMNS:
        op.add_column("vehicles", sa.Column(name, sa.Integer(), nullable=True))
    op.add_column(
        "vehicles",
        sa.Column(
            "trailer_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.alter_column("vehicles", "trailer_count", server_default=None)
    op.drop_index("ix_vehicles_routing_profile_id", table_name="vehicles")
    op.drop_column("vehicles", "routing_profile_id")


def downgrade():
    op.add_column(
        "vehicles", sa.Column("routing_profile_id", sa.UUID(), nullable=True)
    )
    op.create_index(
        "ix_vehicles_routing_profile_id", "vehicles", ["routing_profile_id"]
    )
    op.drop_column("vehicles", "trailer_count")
    for name in reversed(INT_COLUMNS):
        op.drop_column("vehicles", name)
