import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from backend.app.models.doctor import VerificationStatus

class DoctorRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    medical_reg_number: str = Field(..., min_length=3, max_length=100)
    council_name: str = Field(..., min_length=3, max_length=255)
    specialty: str = Field(..., min_length=2, max_length=100)
    years_experience: int = Field(default=0, ge=0, le=70)
    bio: Optional[str] = None

class DoctorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    full_name: str
    medical_reg_number: str
    council_name: str
    specialty: str
    years_experience: int
    bio: Optional[str]
    verification_status: VerificationStatus
    listing_online: bool
    video_enabled: bool
    created_at: datetime
    updated_at: datetime

class DoctorVisibilityUpdate(BaseModel):
    listing_online: Optional[bool] = None
    video_enabled: Optional[bool] = None
