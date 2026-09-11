import uuid

from backend.app.models.base import Base, TimestampMixin
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Chemist(Base, TimestampMixin):
    """Registered pharmacy / chemist partner."""

    __tablename__ = "chemists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    pharmacy_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    license_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    clinic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    address: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    locality: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    pincode: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    contact_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    user = relationship("User")
    clinic = relationship("Clinic")
    prescriptions = relationship(
        "Prescription",
        back_populates="chemist",
        foreign_keys="Prescription.chemist_id",
    )

    def __repr__(self) -> str:
        return f"<Chemist {self.id} {self.pharmacy_name} DL={self.license_number}>"


import backend.app.models.prescription  # noqa: F401, E402

