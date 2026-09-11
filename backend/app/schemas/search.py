import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ClinicCreateOrUpdate(BaseModel):
    name: str
    address: str
    city: str
    locality: str
    pincode: str
    contact_number: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ClinicRead(ClinicCreateOrUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    doctor_id: uuid.UUID
    google_maps_url: str | None = None


class DoctorPublicProfile(BaseModel):
    doctor_id: uuid.UUID
    full_name: str
    specialty: str
    years_experience: int
    bio: str | None = None
    gender: str | None = None
    in_person_fee: Decimal
    video_fee: Decimal = Decimal("0.00")
    listing_online: bool
    video_enabled: bool = False
    rating: float = 4.8
    qualifications: list[str] = Field(default_factory=lambda: ["MBBS"])
    clinic: ClinicRead | None = None
    latitude: float | None = None
    longitude: float | None = None
    google_maps_url: str | None = None


class DoctorSearchResult(BaseModel):
    doctor_id: uuid.UUID
    full_name: str
    specialty: str
    years_experience: int
    bio: str | None = None
    gender: str | None = None
    in_person_fee: Decimal
    video_fee: Decimal = Decimal("0.00")
    listing_online: bool
    video_enabled: bool = False
    rating: float = 4.8
    clinic: ClinicRead | None = None
    latitude: float | None = None
    longitude: float | None = None
    google_maps_url: str | None = None


class DoctorSearchResponse(BaseModel):
    items: list[DoctorSearchResult]
    total: int


class DoctorSearchFilters(BaseModel):
    specialty: str | None = None
    locality: str | None = None
    city: str | None = None
    min_fee: Decimal | None = None
    max_fee: Decimal | None = None
    gender: str | None = None
    video_available: bool | None = None
    available_today: bool | None = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class ToggleListingRequest(BaseModel):
    listing_online: bool | None = None


class ToggleVideoRequest(BaseModel):
    video_enabled: bool | None = None
