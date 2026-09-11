import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from backend.app.models.appointment import AppointmentMode, AppointmentStatus, PaymentStatus


class BookingReserveRequest(BaseModel):
    doctor_id: uuid.UUID
    clinic_id: Optional[uuid.UUID] = None
    slot_start: datetime
    slot_end: datetime
    mode: AppointmentMode


class BookingReserveResponse(BaseModel):
    appointment_id: uuid.UUID
    doctor_id: uuid.UUID
    patient_id: uuid.UUID
    slot_start: datetime
    slot_end: datetime
    mode: AppointmentMode
    fee_amount: Decimal
    status: AppointmentStatus
    payment_status: PaymentStatus
    lock_token: str
    order_id: Optional[str] = None


class BookingConfirmRequest(BaseModel):
    appointment_id: uuid.UUID
    gateway_order_id: str
    gateway_payment_id: str
    gateway_signature: str


class PaymentCreateOrderRequest(BaseModel):
    appointment_id: uuid.UUID


class PaymentCreateOrderResponse(BaseModel):
    appointment_id: uuid.UUID
    order_id: str
    amount: Decimal
    currency: str = "INR"
    key_id: str


class PaymentVerifyRequest(BaseModel):
    appointment_id: uuid.UUID
    gateway_order_id: str
    gateway_payment_id: str
    gateway_signature: str
