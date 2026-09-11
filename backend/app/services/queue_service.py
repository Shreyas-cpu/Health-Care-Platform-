import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from backend.app.models.appointment import Appointment, AppointmentStatus
from backend.app.models.patient import Patient
from backend.app.schemas.queue import QueueAppointmentResponse
from backend.app.services.appointment_state import appointment_state_machine
from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

IST = ZoneInfo("Asia/Kolkata")


async def get_doctor_daily_queue(
    doctor_id: uuid.UUID,
    queue_date: date,
    session: AsyncSession,
) -> list[QueueAppointmentResponse]:
    """Return the doctor's appointments for a calendar day, ordered by slot start."""
    day_start = datetime.combine(queue_date, time.min, tzinfo=IST)
    day_end = day_start + timedelta(days=1)

    stmt = (
        select(Appointment, Patient.full_name)
        .outerjoin(Patient, Patient.user_id == Appointment.patient_id)
        .where(
            and_(
                Appointment.doctor_id == doctor_id,
                Appointment.slot_start >= day_start,
                Appointment.slot_start < day_end,
            )
        )
        .order_by(Appointment.slot_start.asc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    return [
        QueueAppointmentResponse(
            appointment_id=appt.id,
            patient_id=appt.patient_id,
            patient_name=patient_name,
            mode=appt.mode,
            slot_start=appt.slot_start,
            slot_end=appt.slot_end,
            status=appt.status,
            payment_status=appt.payment_status,
            fee_amount=appt.fee_amount,
        )
        for appt, patient_name in rows
    ]


async def _get_owned_appointment(
    appointment_id: uuid.UUID,
    doctor_id: uuid.UUID,
    session: AsyncSession,
) -> Appointment:
    appt = await session.get(Appointment, appointment_id)
    if appt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found.",
        )
    if appt.doctor_id != doctor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to manage this appointment.",
        )
    return appt


async def mark_appointment_complete(
    appointment_id: uuid.UUID,
    doctor_id: uuid.UUID,
    session: AsyncSession,
) -> Appointment:
    """Transition an appointment to COMPLETED via the legal clinical path."""
    appt = await _get_owned_appointment(appointment_id, doctor_id, session)

    # Walk through legal transitions from common queue statuses.
    if appt.status == AppointmentStatus.CONFIRMED:
        appt = await appointment_state_machine.transition(
            appt, AppointmentStatus.CHECKED_IN, session
        )
    if appt.status == AppointmentStatus.CHECKED_IN:
        appt = await appointment_state_machine.transition(
            appt, AppointmentStatus.IN_CONSULTATION, session
        )
    if appt.status == AppointmentStatus.IN_CONSULTATION:
        appt = await appointment_state_machine.transition(
            appt, AppointmentStatus.COMPLETED, session
        )
    elif appt.status != AppointmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot mark complete from status '{appt.status.value}'. "
                "Appointment must be confirmed, checked in, or in consultation."
            ),
        )

    await session.commit()
    await session.refresh(appt)
    return appt


async def mark_appointment_no_show(
    appointment_id: uuid.UUID,
    doctor_id: uuid.UUID,
    session: AsyncSession,
) -> Appointment:
    """Transition an appointment to NO_SHOW."""
    appt = await _get_owned_appointment(appointment_id, doctor_id, session)
    appt = await appointment_state_machine.transition(
        appt, AppointmentStatus.NO_SHOW, session
    )
    await session.commit()
    await session.refresh(appt)
    return appt
