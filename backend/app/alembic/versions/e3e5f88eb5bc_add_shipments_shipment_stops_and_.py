"""Add shipments, shipment stops and shipment documents

Revision ID: e3e5f88eb5bc
Revises: c3e5f7a9b1d2
Create Date: 2026-11-05 15:16:57.898667

"""

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


revision = "e3e5f88eb5bc"
down_revision = "c3e5f7a9b1d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "shipments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("planning_status", sa.String(length=32), nullable=False),
        sa.Column("broker_name", sa.String(length=255), nullable=True),
        sa.Column("broker_contact", sa.String(length=512), nullable=True),
        sa.Column("reference_number", sa.String(length=128), nullable=True),
        sa.Column("total_weight_lbs", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("rate_total", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("rate_currency", sa.String(length=8), nullable=True),
        sa.Column("equipment_type", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extracted_payload", sa.JSON(), nullable=False),
        sa.Column(
            "extraction_confidence", sa.Numeric(precision=4, scale=3), nullable=True
        ),
        sa.Column("field_confidence", sa.JSON(), nullable=False),
        sa.Column("is_manually_edited", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shipments_owner_id", "shipments", ["owner_id"])
    op.create_index("ix_shipments_planning_status", "shipments", ["planning_status"])
    op.create_index("ix_shipments_broker_name", "shipments", ["broker_name"])
    op.create_index("ix_shipments_reference_number", "shipments", ["reference_number"])

    op.create_table(
        "shipment_stops",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("shipment_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("address_raw", sa.String(length=512), nullable=False),
        sa.Column(
            "location", Geography(geometry_type="POINT", srid=4326), nullable=True
        ),
        sa.Column("geocoded_address", sa.String(length=512), nullable=True),
        sa.Column("geocode_error", sa.String(length=512), nullable=True),
        sa.Column("scheduled_at_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference_number", sa.String(length=128), nullable=True),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shipment_id", "sequence", name="uq_shipment_stop_sequence"),
    )
    op.create_index("ix_shipment_stops_shipment_id", "shipment_stops", ["shipment_id"])

    op.create_table(
        "shipment_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("shipment_id", sa.Uuid(), nullable=True),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("raw_llm_response", sa.Text(), nullable=True),
        sa.Column("parse_status", sa.String(length=32), nullable=False),
        sa.Column("parse_error", sa.String(length=1024), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_shipment_documents_shipment_id", "shipment_documents", ["shipment_id"]
    )
    op.create_index(
        "ix_shipment_documents_content_sha256", "shipment_documents", ["content_sha256"]
    )
    op.create_index(
        "ix_shipment_documents_parse_status", "shipment_documents", ["parse_status"]
    )


def downgrade():
    op.drop_index("ix_shipment_documents_parse_status", table_name="shipment_documents")
    op.drop_index(
        "ix_shipment_documents_content_sha256", table_name="shipment_documents"
    )
    op.drop_index("ix_shipment_documents_shipment_id", table_name="shipment_documents")
    op.drop_table("shipment_documents")

    op.drop_index("ix_shipment_stops_shipment_id", table_name="shipment_stops")
    op.drop_table("shipment_stops")

    op.drop_index("ix_shipments_reference_number", table_name="shipments")
    op.drop_index("ix_shipments_broker_name", table_name="shipments")
    op.drop_index("ix_shipments_planning_status", table_name="shipments")
    op.drop_index("ix_shipments_owner_id", table_name="shipments")
    op.drop_table("shipments")
