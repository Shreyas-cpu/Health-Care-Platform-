import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChemistRegisterRequest(BaseModel):
    pharmacy_name: str = Field(..., min_length=2, max_length=255)
    license_number: str = Field(
        ..., min_length=3, max_length=100
    )  # Drug License / DL No
    clinic_id: uuid.UUID | None = None
    address: str = Field(..., min_length=5)
    city: str = Field(..., min_length=2, max_length=100)
    locality: str = Field(..., min_length=2, max_length=100)
    pincode: str = Field(..., min_length=5, max_length=10)
    contact_number: str = Field(..., min_length=8, max_length=20)


class ChemistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    pharmacy_name: str
    license_number: str
    clinic_id: uuid.UUID | None = None
    address: str
    city: str
    locality: str
    pincode: str
    contact_number: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DispensePrescriptionResponse(BaseModel):
    message: str
    prescription_id: uuid.UUID
    dispense_status: str
    dispensed_at: datetime
    dispensed_by_chemist_id: uuid.UUID


class PrescriptionVerificationResponse(BaseModel):
    valid: bool
    prescription_id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    appointment_id: uuid.UUID
    doctor_reg_number: str | None = None
    issued_at: datetime
    digital_signature: str
    dispense_status: str
    dispensed_at: datetime | None = None
    message: str
