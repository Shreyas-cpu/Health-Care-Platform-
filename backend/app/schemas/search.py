import uuid
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ClinicCreateOrUpdate(BaseModel):
    name: str
    address: str
    city: str
    locality: str
    pincode: str
    contact_number: Optional[str] = None


class ClinicRead(ClinicCreateOrUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    doctor_id: uuid.UUID


class DoctorPublicProfile(BaseModel):
    doctor_id: uuid.UUID
    full_name: str
    specialty: str
    years_experience: int
    bio: Optional[str] = None
    gender: Optional[str] = None
    in_person_fee: Decimal
    video_fee: Decimal
    listing_online: bool
    video_enabled: bool
    rating: float = 4.8
    qualifications: List[str] = Field(default_factory=lambda: ["MBBS"])
    clinic: Optional[ClinicRead] = None


class DoctorSearchResult(BaseModel):
    doctor_id: uuid.UUID
    full_name: str
    specialty: str
    years_experience: int
    bio: Optional[str] = None
    gender: Optional[str] = None
    in_person_fee: Decimal
    video_fee: Decimal
    listing_online: bool
    video_enabled: bool
    rating: float = 4.8
    clinic: Optional[ClinicRead] = None


class DoctorSearchResponse(BaseModel):
    items: List[DoctorSearchResult]
    total: int


class DoctorSearchFilters(BaseModel):
    specialty: Optional[str] = None
    locality: Optional[str] = None
    city: Optional[str] = None
    min_fee: Optional[Decimal] = None
    max_fee: Optional[Decimal] = None
    gender: Optional[str] = None
    video_available: Optional[bool] = None
    available_today: Optional[bool] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class ToggleListingRequest(BaseModel):
    listing_online: Optional[bool] = None


class ToggleVideoRequest(BaseModel):
    video_enabled: Optional[bool] = None
