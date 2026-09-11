import uuid
from datetime import datetime

from backend.app.models.user import UserRole
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    phone_number: str = Field(
        ..., pattern=r"^\+?[1-9]\d{9,14}$", description="E.164 or Indian mobile format"
    )
    email: EmailStr | None = None
    role: UserRole = UserRole.PATIENT


class UserCreate(UserBase):
    password: str | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class OTPRequest(BaseModel):
    phone_number: str = Field(..., pattern=r"^\+?[1-9]\d{9,14}$")
    purpose: str = Field(default="login", description="login or registration")


class OTPVerifyRequest(BaseModel):
    phone_number: str = Field(..., pattern=r"^\+?[1-9]\d{9,14}$")
    otp_code: str = Field(..., min_length=6, max_length=6)
    role: UserRole = UserRole.PATIENT
    consent_version: str | None = "1.0"
