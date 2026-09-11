import uuid

from backend.app.models.base import Base, TimestampMixin
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class PatientDocument(Base, TimestampMixin):
    """Uploaded health documents, medical history, lab reports, and past prescriptions."""

    __tablename__ = "patient_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doc_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="medical_history",
        index=True,
    )  # 'lab_report', 'scan', 'past_prescription', 'medical_history', 'other'
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    s3_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    user = relationship("User", foreign_keys=[patient_id])

    def __repr__(self) -> str:
        return f"<PatientDocument {self.id} patient={self.patient_id} type={self.doc_type}>"
