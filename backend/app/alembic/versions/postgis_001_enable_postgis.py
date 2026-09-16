"""Enable PostGIS extensions

Revision ID: postgis_001
Revises: fe56fa70289e
Create Date: 2026-09-16 10:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "postgis_001"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enable PostGIS extensions."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology;")


def downgrade() -> None:
    """Drop PostGIS extensions."""
    op.execute("DROP EXTENSION IF EXISTS postgis_topology;")
    op.execute("DROP EXTENSION IF EXISTS postgis;")
