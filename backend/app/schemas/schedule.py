import uuid
from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AvailabilityCreate(BaseModel):
    clinic_id: uuid.UUID | None = None
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time
    slot_duration_minutes: int = Field(default=15, ge=5, le=120)
    buffer_minutes: int = Field(default=5, ge=0, le=60)
    mode: str = Field(default="both", pattern="^(in_person|video|both)$")


class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doctor_id: uuid.UUID
    clinic_id: uuid.UUID | None = None
    day_of_week: int
    start_time: time
    end_time: time
    slot_duration_minutes: int
    buffer_minutes: int
    mode: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SlotResponse(BaseModel):
    start_time: datetime
    end_time: datetime
    mode: str
    clinic_id: uuid.UUID | None = None
    fee_amount: Decimal
    is_available: bool = True


class LeaveCreate(BaseModel):
    leave_date: date
    reason: str | None = None


class LeaveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doctor_id: uuid.UUID
    leave_date: date
    reason: str | None = None
    created_at: datetime
