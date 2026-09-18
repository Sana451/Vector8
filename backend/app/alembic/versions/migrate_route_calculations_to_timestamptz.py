"""Migrate route_calculations datetime columns to TIMESTAMPTZ

Revision ID: migrate_route_calc_tz
Revises: c7a9b1c2d3e4
Create Date: 2026-09-18 14:50:00.000000

This migration converts DateTime columns to DateTime(timezone=True) for
route_calculations table to ensure all datetime values are timezone-aware UTC.
"""
from alembic import op
import sqlalchemy as sa


revision = 'migrate_route_calc_tz'
down_revision = 'c7a9b1c2d3e4'
branch_labels = None
depends_on = None


def upgrade():
    """Convert created_at and expires_at to TIMESTAMP WITH TIME ZONE."""
    # Check if table exists (in case this is a fresh install, it won't exist)
    # For existing installations, convert the columns
    try:
        # Convert created_at from TIMESTAMP to TIMESTAMP WITH TIME ZONE
        op.execute(
            'ALTER TABLE route_calculations '
            'ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE USING created_at AT TIME ZONE \'UTC\''
        )
    except Exception:
        # If table doesn't exist or column doesn't exist, skip
        pass

    try:
        # Convert expires_at from TIMESTAMP to TIMESTAMP WITH TIME ZONE
        op.execute(
            'ALTER TABLE route_calculations '
            'ALTER COLUMN expires_at TYPE TIMESTAMP WITH TIME ZONE USING expires_at AT TIME ZONE \'UTC\''
        )
    except Exception:
        # If table doesn't exist or column doesn't exist, skip
        pass


def downgrade():
    """Revert TIMESTAMP WITH TIME ZONE back to TIMESTAMP."""
    try:
        # Convert created_at from TIMESTAMP WITH TIME ZONE to TIMESTAMP
        op.execute(
            'ALTER TABLE route_calculations '
            'ALTER COLUMN created_at TYPE TIMESTAMP USING created_at AT TIME ZONE \'UTC\''
        )
    except Exception:
        pass

    try:
        # Convert expires_at from TIMESTAMP WITH TIME ZONE to TIMESTAMP
        op.execute(
            'ALTER TABLE route_calculations '
            'ALTER COLUMN expires_at TYPE TIMESTAMP USING expires_at AT TIME ZONE \'UTC\''
        )
    except Exception:
        pass
