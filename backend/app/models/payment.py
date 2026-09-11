import enum
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class PaymentTransactionStatus(str, enum.Enum):
    PENDING = "pending"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentTransaction(Base, TimestampMixin):
    """Gateway payment record linked to an appointment."""

    __tablename__ = "payment_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    gateway_order_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    gateway_payment_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    status: Mapped[PaymentTransactionStatus] = mapped_column(
        Enum(PaymentTransactionStatus, name="payment_transaction_status", native_enum=True),
        nullable=False,
        default=PaymentTransactionStatus.PENDING,
        index=True,
    )
    method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    refund_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    refund_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<PaymentTransaction {self.id} appt={self.appointment_id} "
            f"status={self.status} amount={self.amount}>"
        )
