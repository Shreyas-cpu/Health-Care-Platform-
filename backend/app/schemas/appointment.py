import uuid
from datetime import datetime
from decimal import Decimal

from backend.app.models.appointment import (
    AppointmentMode,
    AppointmentStatus,
    PaymentStatus,
)
from pydantic import BaseModel, ConfigDict, Field


class AppointmentBase(BaseModel):
    doctor_id: uuid.UUID
    clinic_id: uuid.UUID | None = None
    mode: AppointmentMode
    slot_start: datetime
    slot_end: datetime
    fee_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))

class AppointmentCreate(AppointmentBase):
    pass

class AppointmentRead(AppointmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    status: AppointmentStatus
    payment_status: PaymentStatus
    cancellation_reason: str | None = None
    rescheduled_from_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

class AppointmentTransitionRequest(BaseModel):
    target_status: AppointmentStatus
    reason: str | None = None

class AppointmentCancelRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Mandatory cancellation reason")

class AppointmentRescheduleRequest(BaseModel):
    new_slot_start: datetime
    new_slot_end: datetime
