"""Merge geocoding cache and rest area cache heads

Revision ID: c3d4e5f6a7b8
Revises: a7b8c9d0e1f2, b2c3d4e5f6a7
Create Date: 2026-09-21 12:30:00.000000

"""

revision = "c3d4e5f6a7b8"
down_revision = ("a7b8c9d0e1f2", "b2c3d4e5f6a7")
branch_labels = None
depends_on = None


def upgrade():
    """Merge two independent schema branches without additional DDL."""
    pass


def downgrade():
    """Split the merged heads back into two independent branches."""
    pass
