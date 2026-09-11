import enum
import uuid
from datetime import datetime

from backend.app.models.base import Base, TimestampMixin
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class SessionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    WAITING_ROOM = "waiting_room"
    LIVE = "live"
    COMPLETED = "completed"
    FOLLOW_UP_SCHEDULED = "follow_up_scheduled"


class TeleconsultationSession(Base, TimestampMixin):
    __tablename__ = "teleconsultation_sessions"

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
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status", native_enum=True),
        default=SessionStatus.SCHEDULED,
        nullable=False,
        index=True,
    )
    patient_joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    doctor_joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recording_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    doctor_recording_consent: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    patient_recording_consent: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    appointment = relationship("Appointment", lazy="selectin")
