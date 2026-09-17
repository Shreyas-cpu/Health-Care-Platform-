import uuid
from datetime import datetime
from decimal import Decimal

from backend.app.schemas.prescription import PrescriptionResponse
from pydantic import BaseModel, ConfigDict


class PatientDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    doc_type: str
    file_name: str
    file_size_bytes: int
    notes: str | None = None
    created_at: datetime
    download_url: str | None = None


class PatientVaultResponse(BaseModel):
    uploaded_documents: list[PatientDocumentResponse]
    prescriptions: list[PrescriptionResponse]


class AppointmentHistoryItem(BaseModel):
    id: uuid.UUID | None = None
    appointment_id: uuid.UUID
    doctor_id: uuid.UUID
    doctor_name: str
    specialty: str
    clinic_id: uuid.UUID | None = None
    clinic_name: str | None = None
    clinic_address: str | None = None
    clinic_city: str | None = None
    google_maps_url: str | None = None
    mode: str
    status: str
    slot_start: datetime
    slot_end: datetime
    fee_amount: Decimal
    payment_status: str
    prescription_id: uuid.UUID | None = None
    prescription_download_url: str | None = None
