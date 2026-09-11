import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from backend.app.models.teleconsultation import SessionStatus

SessionStatusEnum = SessionStatus


class TeleconsultationSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    appointment_id: uuid.UUID
    room_name: str
    status: SessionStatusEnum
    patient_joined_at: Optional[datetime] = None
    doctor_joined_at: Optional[datetime] = None
    session_started_at: Optional[datetime] = None
    session_ended_at: Optional[datetime] = None
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
    file_s3_key: Optional[str] = None


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    appointment_id: uuid.UUID
    sender_id: uuid.UUID
    sender_role: str
    message_text: str
    file_s3_key: Optional[str] = None
    created_at: datetime
