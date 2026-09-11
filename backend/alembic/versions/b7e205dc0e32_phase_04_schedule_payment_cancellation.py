"""phase_04_schedule_payment_cancellation

Revision ID: b7e205dc0e32
Revises: a6f194cb9d21
Create Date: 2026-09-11 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7e205dc0e32"
down_revision: Union[str, Sequence[str], None] = "a6f194cb9d21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    payment_transaction_status = sa.Enum(
        "PENDING",
        "CAPTURED",
        "FAILED",
        "REFUNDED",
        name="payment_transaction_status",
    )
    payment_transaction_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "doctor_availability",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("doctor_id", sa.UUID(), nullable=False),
        sa.Column("clinic_id", sa.UUID(), nullable=True),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("slot_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_minutes", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_doctor_availability_clinic_id"),
        "doctor_availability",
        ["clinic_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_doctor_availability_doctor_id"),
        "doctor_availability",
        ["doctor_id"],
        unique=False,
    )

    op.create_table(
        "doctor_leaves",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("doctor_id", sa.UUID(), nullable=False),
        sa.Column("leave_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_doctor_leaves_doctor_id"), "doctor_leaves", ["doctor_id"], unique=False
    )
    op.create_index(
        op.f("ix_doctor_leaves_leave_date"),
        "doctor_leaves",
        ["leave_date"],
        unique=False,
    )

    op.create_table(
        "cancellation_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("cutoff_hours", sa.Integer(), nullable=False),
        sa.Column("refund_percentage", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("fee_deduction", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("appointment_id", sa.UUID(), nullable=False),
        sa.Column("gateway_order_id", sa.String(length=100), nullable=False),
        sa.Column("gateway_payment_id", sa.String(length=100), nullable=True),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "CAPTURED",
                "FAILED",
                "REFUNDED",
                name="payment_transaction_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("method", sa.String(length=50), nullable=True),
        sa.Column("refund_id", sa.String(length=100), nullable=True),
        sa.Column("refund_amount", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["appointment_id"], ["appointments.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_payment_transactions_appointment_id"),
        "payment_transactions",
        ["appointment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_transactions_gateway_order_id"),
        "payment_transactions",
        ["gateway_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_transactions_gateway_payment_id"),
        "payment_transactions",
        ["gateway_payment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_transactions_status"),
        "payment_transactions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_payment_transactions_status"), table_name="payment_transactions"
    )
    op.drop_index(
        op.f("ix_payment_transactions_gateway_payment_id"),
        table_name="payment_transactions",
    )
    op.drop_index(
        op.f("ix_payment_transactions_gateway_order_id"),
        table_name="payment_transactions",
    )
    op.drop_index(
        op.f("ix_payment_transactions_appointment_id"),
        table_name="payment_transactions",
    )
    op.drop_table("payment_transactions")
    op.drop_table("cancellation_policies")
    op.drop_index(op.f("ix_doctor_leaves_leave_date"), table_name="doctor_leaves")
    op.drop_index(op.f("ix_doctor_leaves_doctor_id"), table_name="doctor_leaves")
    op.drop_table("doctor_leaves")
    op.drop_index(
        op.f("ix_doctor_availability_doctor_id"), table_name="doctor_availability"
    )
    op.drop_index(
        op.f("ix_doctor_availability_clinic_id"), table_name="doctor_availability"
    )
    op.drop_table("doctor_availability")
    sa.Enum(name="payment_transaction_status").drop(op.get_bind(), checkfirst=True)
