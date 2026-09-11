import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class SendOTPRequest(BaseModel):
    phone_number: str = Field(...)


class VerifyOTPRequest(BaseModel):
    phone_number: str
    otp_code: str
    full_name: str | None = None
    consent_version: str | None = "v1.0"


class PatientProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    phone_number: str
    full_name: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    created_at: datetime | None = None


class PatientAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    patient: PatientProfileRead


class PatientProfileUpdate(BaseModel):
    full_name: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
