import enum
import uuid
from datetime import datetime

from backend.app.models.base import Base
from backend.app.models.doctor import VerificationStatus
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class DocumentType(str, enum.Enum):
    MEDICAL_REG_CERT = "medical_reg_cert"
    DEGREE_CERT = "degree_cert"
    CLINIC_REG = "clinic_reg"
    IDENTITY_PROOF = "identity_proof"

class DoctorDocument(Base):
    __tablename__ = "doctor_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type", native_enum=True),
        nullable=False
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    s3_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    doctor = relationship("Doctor", back_populates="documents")

    def __repr__(self) -> str:
        return f"<DoctorDocument {self.id} doc_type={self.doc_type} s3_key={self.s3_key}>"

class VerificationReview(Base):
    __tablename__ = "verification_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    reviewer_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    previous_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status", native_enum=True),
        nullable=False
    )
    new_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status", native_enum=True),
        nullable=False
    )
    reason_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    doctor = relationship("Doctor", back_populates="reviews")

    def __repr__(self) -> str:
        return f"<VerificationReview {self.id} doctor={self.doctor_id} {self.previous_status}->{self.new_status}>"
