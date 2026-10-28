"""add origin and destination labels to trip_plan

Revision ID: b7c2d4e6f8a1
Revises: e4a7c21b9d35
Create Date: 2026-10-29 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7c2d4e6f8a1"
down_revision = "e4a7c21b9d35"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "trip_plans",
        sa.Column("origin_label", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "trip_plans",
        sa.Column("destination_label", sa.String(length=512), nullable=True),
    )


def downgrade():
    op.drop_column("trip_plans", "destination_label")
    op.drop_column("trip_plans", "origin_label")
