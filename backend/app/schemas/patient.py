import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SendOTPRequest(BaseModel):
    phone_number: str = Field(...)


class VerifyOTPRequest(BaseModel):
    phone_number: str
    otp_code: str
    full_name: Optional[str] = None
    consent_version: Optional[str] = "v1.0"


class PatientProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    phone_number: str
    full_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    created_at: Optional[datetime] = None


class PatientAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    patient: PatientProfileRead


class PatientProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
