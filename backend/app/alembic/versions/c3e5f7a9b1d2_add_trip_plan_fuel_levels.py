"""add trip plan starting and remaining fuel

Revision ID: c3e5f7a9b1d2
Revises: b7c2d4e6f8a1
Create Date: 2026-10-29 15:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3e5f7a9b1d2"
down_revision = "b7c2d4e6f8a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trip_plans",
        sa.Column("initial_fuel_gallons", sa.Numeric(10, 4), nullable=True),
    )
    op.add_column(
        "trip_plans",
        sa.Column("remaining_fuel_gallons", sa.Numeric(10, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("trip_plans", "remaining_fuel_gallons")
    op.drop_column("trip_plans", "initial_fuel_gallons")
