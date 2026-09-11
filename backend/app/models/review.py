import enum
import uuid

from backend.app.models.base import Base, TimestampMixin
from sqlalchemy import Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class ReviewStatus(str, enum.Enum):
    PUBLISHED = "published"
    FLAGGED = "flagged"
    HIDDEN = "hidden"
    REMOVED = "removed"


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    review_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status", native_enum=True),
        default=ReviewStatus.PUBLISHED,
        nullable=False,
        index=True,
    )
    doctor = relationship("Doctor", back_populates="patient_reviews")
    appointment = relationship("Appointment")
    patient = relationship("User")


import backend.app.models.appointment  # noqa: F401
