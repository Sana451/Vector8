"""add user role and driver_profiles table

Revision ID: e4a7c21b9d35
Revises: 87d9a1a52cca
Create Date: 2026-10-29 09:12:03.114820

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e4a7c21b9d35"
down_revision = "87d9a1a52cca"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user",
        sa.Column(
            "role", sa.String(length=32), nullable=False, server_default="dispatcher"
        ),
    )
    op.execute("UPDATE \"user\" SET role = 'admin' WHERE is_superuser")
    op.alter_column("user", "role", server_default=None)
    op.create_index(op.f("ix_user_role"), "user", ["role"], unique=False)

    op.create_table(
        "driver_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("license_number", sa.String(length=64), nullable=True),
        sa.Column("default_vehicle_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["default_vehicle_id"], ["vehicles.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_driver_profiles_default_vehicle_id"),
        "driver_profiles",
        ["default_vehicle_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_driver_profiles_default_vehicle_id"), table_name="driver_profiles"
    )
    op.drop_table("driver_profiles")
    op.drop_index(op.f("ix_user_role"), table_name="user")
    op.drop_column("user", "role")
