import uuid
from datetime import datetime
from decimal import Decimal

from backend.app.models.appointment import AppointmentMode, AppointmentStatus, PaymentStatus
from pydantic import BaseModel, ConfigDict


class QueueAppointmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    mode: AppointmentMode
    slot_start: datetime
    slot_end: datetime
    status: AppointmentStatus
    payment_status: PaymentStatus
    fee_amount: Decimal
