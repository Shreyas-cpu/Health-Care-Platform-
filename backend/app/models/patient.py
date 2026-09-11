import uuid
from datetime import date

from backend.app.models.base import Base, TimestampMixin
from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship


class Patient(Base, TimestampMixin):
    """Patient-specific identity data, keyed by its owning user account."""

    __tablename__ = "patients"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    user = relationship("User", lazy="selectin", backref=backref("patient_profile", uselist=False))
