import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.appointment import Appointment, AppointmentMode, AppointmentStatus, PaymentStatus
from backend.app.models.teleconsultation import SessionStatus
from backend.app.models.user import User, UserRole
from backend.app.services.chat_service import get_chat_history, save_chat_message
from backend.app.services.livekit_client import generate_livekit_token
from backend.app.services.teleconsultation_service import (
    check_waiting_room_timeout, doctor_start_session, end_session, get_or_create_session,
    patient_enter_waiting_room, update_recording_consent,
)


async def _confirmed_appointment(session: AsyncSession) -> tuple[Appointment, User, User]:
    patient = User(id=uuid.uuid4(), phone_number=f"+9195{uuid.uuid4().int % 100000000:08d}", role=UserRole.PATIENT, is_active=True)
    doctor = User(id=uuid.uuid4(), phone_number=f"+9196{uuid.uuid4().int % 100000000:08d}", role=UserRole.DOCTOR, is_active=True)
    session.add(patient)
    session.add(doctor)
    await session.commit()

    appointment = Appointment(
        id=uuid.uuid4(), patient_id=patient.id, doctor_id=doctor.id, mode=AppointmentMode.VIDEO,
        status=AppointmentStatus.CONFIRMED, slot_start=datetime.now(timezone.utc),
        slot_end=datetime.now(timezone.utc) + timedelta(minutes=30), fee_amount=Decimal("400.00"),
        payment_status=PaymentStatus.CAPTURED,
    )
    session.add(appointment)
    await session.commit()
    return appointment, patient, doctor


@pytest.mark.asyncio
async def test_dual_state_sync_lifecycle(db_session: AsyncSession):
    appointment, patient, doctor = await _confirmed_appointment(db_session)
    waiting = await patient_enter_waiting_room(db_session, appointment.id, patient.id)
    await db_session.refresh(appointment)
    assert appointment.status == AppointmentStatus.CHECKED_IN
    assert waiting.status == SessionStatus.WAITING_ROOM

    live = await doctor_start_session(db_session, appointment.id, doctor.id)
    await db_session.refresh(appointment)
    assert appointment.status == AppointmentStatus.IN_CONSULTATION
    assert live.status == SessionStatus.LIVE

    completed = await end_session(db_session, appointment.id, patient.id)
    await db_session.refresh(appointment)
    assert appointment.status == AppointmentStatus.COMPLETED
    assert completed.status == SessionStatus.COMPLETED


@pytest.mark.asyncio
async def test_recording_consent_dual_party_gate(db_session: AsyncSession):
    appointment, patient, doctor = await _confirmed_appointment(db_session)
    one_party = await update_recording_consent(db_session, appointment.id, doctor.id, True)
    assert one_party.recording_enabled is False
    both_parties = await update_recording_consent(db_session, appointment.id, patient.id, True)
    assert both_parties.recording_enabled is True
    revoked = await update_recording_consent(db_session, appointment.id, patient.id, False)
    assert revoked.recording_enabled is False


def test_livekit_token_generation():
    token = generate_livekit_token("room-123", "patient-123", "Patient", "patient")
    claims = jwt.decode(token, settings.LIVEKIT_API_SECRET, algorithms=["HS256"], audience=None)
    assert claims["sub"] == "patient-123"
    assert claims["video"]["room"] == "room-123"
    assert claims["video"]["roomJoin"] is True
    assert claims["video"]["canPublish"] is True


@pytest.mark.asyncio
async def test_in_call_chat_persistence(db_session: AsyncSession):
    appointment, patient, _ = await _confirmed_appointment(db_session)
    message = await save_chat_message(db_session, appointment.id, patient.id, "patient", "Can you hear me?")
    history = await get_chat_history(db_session, appointment.id)
    assert [item.id for item in history] == [message.id]
    assert history[0].message_text == "Can you hear me?"


@pytest.mark.asyncio
async def test_waiting_room_timeout_fail_safe(db_session: AsyncSession):
    appointment, patient, _ = await _confirmed_appointment(db_session)
    waiting = await patient_enter_waiting_room(db_session, appointment.id, patient.id)
    waiting.patient_joined_at = datetime.now(timezone.utc) - timedelta(minutes=21)
    await db_session.commit()
    assert await check_waiting_room_timeout(db_session, appointment.id) == {
        "timeout": True, "eligible_for_refund": True, "eligible_for_reschedule": True,
    }
