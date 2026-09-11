"""phase_03_patient_clinic_and_fees

Revision ID: a6f194cb9d21
Revises: 483329b6e015
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a6f194cb9d21"
down_revision: Union[str, Sequence[str], None] = "483329b6e015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.add_column("doctors", sa.Column("gender", sa.String(length=20), nullable=True))
    op.add_column("doctors", sa.Column("in_person_fee", sa.Numeric(10, 2), server_default="500.00", nullable=False))
    op.add_column("doctors", sa.Column("video_fee", sa.Numeric(10, 2), server_default="400.00", nullable=False))
    op.create_table(
        "clinics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("doctor_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("locality", sa.String(length=100), nullable=False),
        sa.Column("pincode", sa.String(length=10), nullable=False),
        sa.Column("contact_number", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("doctor_id"),
    )
    op.create_index(op.f("ix_clinics_doctor_id"), "clinics", ["doctor_id"], unique=True)
    op.create_index(op.f("ix_clinics_city"), "clinics", ["city"], unique=False)
    op.create_index(op.f("ix_clinics_locality"), "clinics", ["locality"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_clinics_locality"), table_name="clinics")
    op.drop_index(op.f("ix_clinics_city"), table_name="clinics")
    op.drop_index(op.f("ix_clinics_doctor_id"), table_name="clinics")
    op.drop_table("clinics")
    op.drop_column("doctors", "video_fee")
    op.drop_column("doctors", "in_person_fee")
    op.drop_column("doctors", "gender")
    op.drop_table("patients")
