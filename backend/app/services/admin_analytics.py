from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.appointment import Appointment, AppointmentStatus, PaymentStatus
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.payment import PaymentTransaction, PaymentTransactionStatus
from backend.app.schemas.admin import PlatformTelemetryResponse

async def get_platform_telemetry(session: AsyncSession) -> PlatformTelemetryResponse:
    verified = (await session.execute(select(func.count(Doctor.user_id)).where(Doctor.verification_status == VerificationStatus.VERIFIED))).scalar_one()
    confirmed = (await session.execute(select(func.count(Appointment.id)).where(Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.CHECKED_IN, AppointmentStatus.IN_CONSULTATION, AppointmentStatus.COMPLETED])))).scalar_one()
    completed = (await session.execute(select(func.count(Appointment.id)).where(Appointment.status == AppointmentStatus.COMPLETED))).scalar_one()
    gtv = (await session.execute(select(func.coalesce(func.sum(PaymentTransaction.amount), 0)).where(PaymentTransaction.status == PaymentTransactionStatus.CAPTURED))).scalar_one()
    if not gtv:
        gtv = (await session.execute(select(func.coalesce(func.sum(Appointment.fee_amount), 0)).where(Appointment.payment_status == PaymentStatus.CAPTURED))).scalar_one()
    return PlatformTelemetryResponse(total_verified_doctors=int(verified), total_confirmed_bookings=int(confirmed), total_completed_consultations=int(completed), gross_transaction_value=Decimal(str(gtv or 0)))
