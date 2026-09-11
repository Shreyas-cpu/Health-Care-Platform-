import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PrescriptionItemCreate(BaseModel):
    drug_name: str = Field(..., min_length=1, max_length=255)
    dosage: str = Field(..., min_length=1, max_length=100)
    frequency: str = Field(..., min_length=1, max_length=50)
    duration_days: int = Field(..., ge=1)
    instructions: str | None = Field(default=None, max_length=255)


class PrescriptionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    drug_name: str
    dosage: str
    frequency: str
    duration_days: int
    instructions: str | None = None


class PrescriptionCreate(BaseModel):
    appointment_id: uuid.UUID
    diagnosis: str = Field(..., min_length=1)
    clinical_notes: str | None = None
    chemist_id: uuid.UUID | None = None
    items: list[PrescriptionItemCreate] = Field(..., min_length=1)


class PrescriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    appointment_id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    diagnosis: str
    clinical_notes: str | None = None
    pdf_s3_key: str | None = None
    issued_at: datetime
    chemist_id: uuid.UUID | None = None
    digital_signature: str
    digital_signature_timestamp: datetime
    dispense_status: str = "pending"
    dispensed_at: datetime | None = None
    dispensed_by_chemist_id: uuid.UUID | None = None
    items: list[PrescriptionItemResponse]
    download_url: str | None = None
    created_at: datetime
    updated_at: datetime


class DrugMasterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_name: str
    generic_name: str
    dosage_form: str
    is_telemedicine_restricted: bool
