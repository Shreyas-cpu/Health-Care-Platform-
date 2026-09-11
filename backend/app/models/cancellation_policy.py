import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, TimestampMixin


class CancellationPolicy(Base, TimestampMixin):
    """Configurable cancellation / refund eligibility rules."""

    __tablename__ = "cancellation_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(100), default="Standard Cancellation Policy", nullable=False
    )
    cutoff_hours: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    refund_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("100.00"), nullable=False
    )
    fee_deduction: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<CancellationPolicy {self.id} name={self.name} "
            f"cutoff={self.cutoff_hours}h refund={self.refund_percentage}%>"
        )
