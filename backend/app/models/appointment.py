import enum
import uuid
from datetime import datetime
from decimal import Decimal

from backend.app.models.base import Base, TimestampMixin
from sqlalchemy import (
    Boolean, DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class AppointmentMode(str, enum.Enum):
    IN_PERSON = "in_person"
    VIDEO = "video"

class AppointmentStatus(str, enum.Enum):
    """
    PRD Section 2A: 8-state appointment lifecycle
    """
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    CHECKED_IN = "checked_in"
    IN_CONSULTATION = "in_consultation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    CAPTURED = "captured"
    REFUNDED = "refunded"
    FAILED = "failed"

class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True
    )
    mode: Mapped[AppointmentMode] = mapped_column(
        Enum(AppointmentMode, name="appointment_mode", native_enum=True),
        nullable=False
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status", native_enum=True),
        nullable=False,
        default=AppointmentStatus.REQUESTED,
        index=True
    )
    slot_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    slot_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", native_enum=True),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    rescheduled_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True
    )
    lock_token: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    __table_args__ = (
        Index("ix_appointments_doctor_slot", "doctor_id", "slot_start", "slot_end"),
    )

    def __repr__(self) -> str:
        return f"<Appointment {self.id} doctor={self.doctor_id} status={self.status} slot={self.slot_start}>"
