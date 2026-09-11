import uuid
from datetime import UTC, datetime, timedelta

from backend.app.core.redis import publish_event
from backend.app.models.appointment import Appointment, AppointmentStatus
from backend.app.models.teleconsultation import SessionStatus, TeleconsultationSession
from backend.app.services.appointment_state import appointment_state_machine
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _appointment_or_404(
    session: AsyncSession, appointment_id: uuid.UUID
) -> Appointment:
    appointment = (
        await session.execute(
            select(Appointment).where(Appointment.id == appointment_id)
        )
    ).scalar_one_or_none()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found."
        )
    return appointment


async def get_or_create_session(
    session: AsyncSession, appointment_id: uuid.UUID
) -> TeleconsultationSession:
    tele_session = (
        await session.execute(
            select(TeleconsultationSession).where(
                TeleconsultationSession.appointment_id == appointment_id
            )
        )
    ).scalar_one_or_none()
    if tele_session is None:
        tele_session = TeleconsultationSession(
            appointment_id=appointment_id, room_name=f"room_{appointment_id}"
        )
        session.add(tele_session)
        await session.flush()
    return tele_session


async def _publish(event_type: str, data: dict) -> None:
    try:
        await publish_event("appointment:events", event_type, data)
    except Exception:
        # The state is durable in PostgreSQL even if the optional real-time bridge is unavailable.
        pass


async def patient_enter_waiting_room(
    session: AsyncSession, appointment_id: uuid.UUID, user_id: uuid.UUID
) -> TeleconsultationSession:
    appointment = await _appointment_or_404(session, appointment_id)
    if appointment.patient_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the appointment patient may enter the waiting room.",
        )
    if appointment.status not in {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CHECKED_IN,
    }:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Appointment is not ready for check-in.",
        )
    if appointment.status == AppointmentStatus.CONFIRMED:
        await appointment_state_machine.transition(
            appointment, AppointmentStatus.CHECKED_IN, session
        )

    tele_session = await get_or_create_session(session, appointment_id)
    tele_session.status = SessionStatus.WAITING_ROOM
    tele_session.patient_joined_at = datetime.now(UTC)
    await _publish(
        "doctor_notified_patient_waiting",
        {"appointment_id": str(appointment_id), "patient_id": str(user_id)},
    )
    await session.commit()
    await session.refresh(tele_session)
    return tele_session


async def doctor_start_session(
    session: AsyncSession, appointment_id: uuid.UUID, user_id: uuid.UUID
) -> TeleconsultationSession:
    appointment = await _appointment_or_404(session, appointment_id)
    if appointment.doctor_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the appointment doctor may start this session.",
        )
    if appointment.status not in {
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.CHECKED_IN,
    }:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Appointment is not ready to start.",
        )
    if appointment.status == AppointmentStatus.CONFIRMED:
        await appointment_state_machine.transition(
            appointment, AppointmentStatus.CHECKED_IN, session
        )
    await appointment_state_machine.transition(
        appointment, AppointmentStatus.IN_CONSULTATION, session
    )

    tele_session = await get_or_create_session(session, appointment_id)
    now = datetime.now(UTC)
    tele_session.status = SessionStatus.LIVE
    tele_session.doctor_joined_at = now
    tele_session.session_started_at = now
    await _publish(
        "session_live",
        {"appointment_id": str(appointment_id), "doctor_id": str(user_id)},
    )
    await session.commit()
    await session.refresh(tele_session)
    return tele_session


async def end_session(
    session: AsyncSession, appointment_id: uuid.UUID, user_id: uuid.UUID
) -> TeleconsultationSession:
    appointment = await _appointment_or_404(session, appointment_id)
    if user_id not in {appointment.patient_id, appointment.doctor_id}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a participant in this appointment.",
        )
    await appointment_state_machine.transition(
        appointment, AppointmentStatus.COMPLETED, session
    )
    tele_session = await get_or_create_session(session, appointment_id)
    tele_session.status = SessionStatus.COMPLETED
    tele_session.session_ended_at = datetime.now(UTC)
    await _publish(
        "session_completed",
        {"appointment_id": str(appointment_id), "user_id": str(user_id)},
    )
    await session.commit()
    await session.refresh(tele_session)
    return tele_session


async def update_recording_consent(
    session: AsyncSession, appointment_id: uuid.UUID, user_id: uuid.UUID, consent: bool
) -> TeleconsultationSession:
    appointment = await _appointment_or_404(session, appointment_id)
    tele_session = await get_or_create_session(session, appointment_id)
    if user_id == appointment.doctor_id:
        tele_session.doctor_recording_consent = consent
    elif user_id == appointment.patient_id:
        tele_session.patient_recording_consent = consent
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a participant in this appointment.",
        )
    tele_session.recording_enabled = bool(
        tele_session.doctor_recording_consent and tele_session.patient_recording_consent
    )
    await session.commit()
    await session.refresh(tele_session)
    return tele_session


async def check_waiting_room_timeout(
    session: AsyncSession, appointment_id: uuid.UUID
) -> dict:
    tele_session = (
        await session.execute(
            select(TeleconsultationSession).where(
                TeleconsultationSession.appointment_id == appointment_id
            )
        )
    ).scalar_one_or_none()
    if (
        tele_session
        and tele_session.status == SessionStatus.WAITING_ROOM
        and tele_session.patient_joined_at
        and tele_session.patient_joined_at <= datetime.now(UTC) - timedelta(minutes=20)
        and tele_session.doctor_joined_at is None
    ):
        return {
            "timeout": True,
            "eligible_for_refund": True,
            "eligible_for_reschedule": True,
        }
    return {"timeout": False}
