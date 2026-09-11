import enum
import uuid
from decimal import Decimal

from backend.app.models.base import Base, TimestampMixin
from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class VerificationStatus(str, enum.Enum):
    """
    PRD Section 2D: 6-state doctor verification pipeline
    """
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    INFO_REQUESTED = "info_requested"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUSPENDED = "suspended"

class Doctor(Base, TimestampMixin):
    __tablename__ = "doctors"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    medical_reg_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False
    )
    council_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    specialty: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False
    )
    years_experience: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    bio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    in_person_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("500.00"), nullable=False
    )
    video_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("400.00"), nullable=False
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status", native_enum=True),
        nullable=False,
        default=VerificationStatus.SUBMITTED,
        index=True
    )
    listing_online: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    video_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    average_rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.00"), nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    documents = relationship("DoctorDocument", back_populates="doctor", cascade="all, delete-orphan", lazy="selectin")
    reviews = relationship("VerificationReview", back_populates="doctor", cascade="all, delete-orphan", lazy="selectin")
    clinic = relationship("Clinic", back_populates="doctor", uselist=False, lazy="selectin", cascade="all, delete-orphan")
    patient_reviews = relationship("Review", back_populates="doctor", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Doctor {self.user_id} name={self.full_name} status={self.verification_status} online={self.listing_online}>"

import backend.app.models.review  # noqa: F401, E402


import backend.app.models.clinic  # noqa: F401, E402
import backend.app.models.verification  # noqa: F401, E402
