import uuid
from datetime import datetime

from backend.app.models.teleconsultation import SessionStatus
from pydantic import BaseModel, ConfigDict

SessionStatusEnum = SessionStatus


class TeleconsultationSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    appointment_id: uuid.UUID
    room_name: str
    status: SessionStatusEnum
    patient_joined_at: datetime | None = None
    doctor_joined_at: datetime | None = None
    session_started_at: datetime | None = None
    session_ended_at: datetime | None = None
    recording_enabled: bool
    doctor_recording_consent: bool
    patient_recording_consent: bool


class LiveKitTokenResponse(BaseModel):
    token: str
    room_name: str
    livekit_url: str


class RecordingConsentRequest(BaseModel):
    consent: bool


class ChatMessageCreate(BaseModel):
    message_text: str
    file_s3_key: str | None = None


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    appointment_id: uuid.UUID
    sender_id: uuid.UUID
    sender_role: str
    message_text: str
    file_s3_key: str | None = None
    created_at: datetime
