"""Add last_imported_at to fuel_stations

Revision ID: 6f2b8c1d4e90
Revises: 0253fbda0416
Create Date: 2026-09-23 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "6f2b8c1d4e90"
down_revision = "0253fbda0416"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "fuel_stations",
        sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("fuel_stations", "last_imported_at")
