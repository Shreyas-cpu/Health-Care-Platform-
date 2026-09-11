import uuid
from pydantic import BaseModel, Field

from backend.app.models.user import UserRole


class FirebaseLoginRequest(BaseModel):
    id_token: str = Field(..., description="Firebase ID Token (JWT) acquired from Firebase Client SDK")
    role: UserRole = Field(default=UserRole.PATIENT, description="Target role (patient, doctor, chemist)")
    full_name: str | None = Field(default=None, description="Display name for new patient/user creation")
    consent_version: str = Field(default="v1.0", description="DPDP Act patient consent policy version")


class FirebaseLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    firebase_uid: str
    user_id: uuid.UUID
    role: UserRole
    phone_number: str | None = None
    email: str | None = None
    is_new_user: bool


class FirebaseVerifyTokenRequest(BaseModel):
    id_token: str = Field(..., description="Firebase ID Token to decode and verify")


class FirebaseVerifyTokenResponse(BaseModel):
    valid: bool
    uid: str
    email: str | None = None
    phone_number: str | None = None
    name: str | None = None


class FirebaseBindPhoneRequest(BaseModel):
    phone_number: str = Field(..., description="E.164 phone number to bind to the user profile")
