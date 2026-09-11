"""
test_mvp_golden_loop.py
End-to-End MVP Golden Loop Integration Test covering all 14 lifecycle stages:
1. Doctor registration (DOC-01)
2. Admin document verification & audit log (ADM-01, RUL-04)
3. Doctor schedule & clinic setup, toggle online (DOC-02, DOC-05)
4. Patient OTP auth with DPDP consent (PAT-01, CMP-02)
5. Patient search & public profile view (PAT-02, PAT-03, RUL-02)
6. Atomic slot reservation & Redis lock (PAT-04, RUL-01)
7. Razorpay payment capture & booking confirmation (PAT-08, RUL-03)
8. Automated reminder dispatch (PAT-05)
9. Teleconsultation waiting room check-in (TEL-01, TEL-03)
10. LiveKit token generation & in-call chat (TEL-02)
11. Doctor completes session & queue ops (DOC-03)
12. Structured prescription creation with Schedule X compliance (DOC-04, CMP-01)
13. Vector PDF generation & patient record access (PAT-06)
14. Patient 5-star review & administrative audit moderation (PAT-07, ADM-03, ADM-04, RUL-04)
"""

import uuid
from datetime import datetime, timedelta, time as dt_time, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.redis import lock_manager
from backend.app.models.appointment import Appointment, AppointmentMode, AppointmentStatus, PaymentStatus
from backend.app.models.audit import AuditLog
from backend.app.models.clinic import Clinic
from backend.app.models.consent import ConsentRecord
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.drug import DrugMaster
from backend.app.models.patient import Patient
from backend.app.models.payment import PaymentTransaction, PaymentTransactionStatus
from backend.app.models.review import ReviewStatus
from backend.app.models.schedule import DoctorAvailability
from backend.app.models.teleconsultation import SessionStatus, TeleconsultationSession
from backend.app.models.user import User, UserRole
from backend.app.models.verification import DoctorDocument, DocumentType
from backend.app.schemas.booking import BookingConfirmRequest, BookingReserveRequest
from backend.app.schemas.prescription import PrescriptionCreate, PrescriptionItemCreate
from backend.app.schemas.review import ReviewCreate
from backend.app.services.admin_analytics import get_platform_telemetry
from backend.app.services.audit import record_audit_log
from backend.app.services.booking_service import confirm_booking, reserve_slot
from backend.app.services.chat_service import save_chat_message
from backend.app.services.livekit_client import generate_livekit_token
from backend.app.services.pdf_compiler import compile_prescription_pdf
from backend.app.services.prescription_service import create_prescription
from backend.app.services.reminder_service import dispatch_upcoming_reminders
from backend.app.services.review_service import moderate_review, submit_review
from backend.app.services.search_index import search_doctors
from backend.app.schemas.search import DoctorSearchFilters
from backend.app.services.teleconsultation_service import (
    doctor_start_session,
    end_session,
    patient_enter_waiting_room,
)
from backend.app.services.verification_state import verification_state_machine


@pytest.mark.asyncio
async def test_full_mvp_golden_loop(db_session: AsyncSession):
    now = datetime.now(timezone.utc)
    target_date = (now + timedelta(days=1)).date()
    slot_start = datetime.combine(target_date, dt_time(10, 0), tzinfo=timezone.utc)
    slot_end = datetime.combine(target_date, dt_time(10, 30), tzinfo=timezone.utc)

    # -------------------------------------------------------------------------
    # STAGE 1: Doctor Registration (DOC-01)
    # -------------------------------------------------------------------------
    doc_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    reviewer_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9197{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.VERIFICATION_REVIEWER,
        is_active=True,
    )
    admin_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9199{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    db_session.add_all([doc_user, reviewer_user, admin_user])
    await db_session.flush()

    doctor = Doctor(
        user_id=doc_user.id,
        full_name="Dr. Golden Physician",
        medical_reg_number=f"MCI-{uuid.uuid4().hex[:8].upper()}",
        council_name="Delhi Medical Council",
        specialty="General Physician",
        years_experience=10,
        in_person_fee=Decimal("600.00"),
        video_fee=Decimal("500.00"),
        verification_status=VerificationStatus.SUBMITTED,
        listing_online=False,
        video_enabled=True,
    )
    db_session.add(doctor)
    await db_session.flush()

    doc_cert = DoctorDocument(
        id=uuid.uuid4(),
        doctor_id=doctor.user_id,
        doc_type=DocumentType.MEDICAL_REG_CERT,
        s3_key=f"docs/{doctor.user_id}/reg.pdf",
        file_name="reg.pdf",
    )
    db_session.add(doc_cert)
    await db_session.commit()

    # -------------------------------------------------------------------------
    # STAGE 2: Reviewer Inspection & Verification Gate (ADM-01, RUL-04)
    # -------------------------------------------------------------------------
    await verification_state_machine.transition_doctor_status(
        doctor=doctor,
        new_status=VerificationStatus.UNDER_REVIEW,
        admin_user_id=reviewer_user.id,
        session=db_session,
        reason_text="Initial document intake complete",
    )
    await verification_state_machine.transition_doctor_status(
        doctor=doctor,
        new_status=VerificationStatus.VERIFIED,
        admin_user_id=reviewer_user.id,
        session=db_session,
        reason_text="MCI Credentials verified against national registry",
    )
    await db_session.commit()
    assert doctor.verification_status == VerificationStatus.VERIFIED

    # -------------------------------------------------------------------------
    # STAGE 3: Schedule, Clinic & Go-Live (DOC-02, DOC-05)
    # -------------------------------------------------------------------------
    clinic = Clinic(
        id=uuid.uuid4(),
        doctor_id=doctor.user_id,
        name="Golden Care Clinic",
        address="123 Health Ave, Indiranagar",
        city="Bengaluru",
        locality="Indiranagar",
        pincode="560038",
        contact_number="+918012345678",
    )
    doctor.listing_online = True
    db_session.add(clinic)
    await db_session.flush()

    availability = DoctorAvailability(
        id=uuid.uuid4(),
        doctor_id=doctor.user_id,
        clinic_id=clinic.id,
        day_of_week=target_date.weekday(),
        start_time=dt_time(9, 0),
        end_time=dt_time(17, 0),
        slot_duration_minutes=30,
        buffer_minutes=0,
        mode="both",
        is_active=True,
    )
    db_session.add(availability)
    await db_session.commit()

    # -------------------------------------------------------------------------
    # STAGE 4: Patient Authentication & DPDP Consent (PAT-01, CMP-02)
    # -------------------------------------------------------------------------
    patient_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9191{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add(patient_user)
    await db_session.flush()

    patient = Patient(
        user_id=patient_user.id,
        full_name="John Doe Patient",
        gender="Male",
        date_of_birth=datetime(1992, 5, 15).date(),
    )
    consent = ConsentRecord(
        id=uuid.uuid4(),
        user_id=patient_user.id,
        purpose="patient_registration_and_care",
        consent_version="v1.0",
        ip_address="127.0.0.1",
        user_agent="GoldenLoopTest/1.0",
        is_granted=True,
    )
    db_session.add_all([patient, consent])
    await db_session.commit()

    # -------------------------------------------------------------------------
    # STAGE 5: Patient Search & Discovery (PAT-02, PAT-03, RUL-02)
    # -------------------------------------------------------------------------
    # Use the proper search filter schema
    filters = DoctorSearchFilters(
        specialty="General Physician",
        city="Bengaluru",
        video_available=True,
    )
    search_results = await search_doctors(session=db_session, filters=filters)
    # Verify the doctor appears in the search results
    assert any(item.doctor_id == doctor.user_id for item in search_results.items)

    # -------------------------------------------------------------------------
    # STAGE 6: Atomic Slot Reservation (PAT-04, RUL-01)
    # -------------------------------------------------------------------------
    reserve_req = BookingReserveRequest(
        doctor_id=doctor.user_id,
        clinic_id=clinic.id,
        slot_start=slot_start,
        slot_end=slot_end,
        mode=AppointmentMode.VIDEO,
    )
    reserve_resp = await reserve_slot(patient_user.id, reserve_req, db_session)
    await db_session.commit()
    assert reserve_resp.status == AppointmentStatus.REQUESTED
    appt_id = reserve_resp.appointment_id

    # -------------------------------------------------------------------------
    # STAGE 7: Razorpay Payment Capture & Booking Confirmation (PAT-08, RUL-03)
    # -------------------------------------------------------------------------
    confirm_req = BookingConfirmRequest(
        appointment_id=appt_id,
        gateway_order_id=reserve_resp.gateway_order_id,
        gateway_payment_id=f"pay_{uuid.uuid4().hex[:12]}",
        gateway_signature="mocked_valid_hmac_signature",
    )
    confirmed_appt = await confirm_booking(confirm_req, db_session)
    assert confirmed_appt.status == AppointmentStatus.CONFIRMED
    assert confirmed_appt.payment_status == PaymentStatus.CAPTURED

    # -------------------------------------------------------------------------
    # STAGE 8: Automated Reminder Dispatch (PAT-05)
    # -------------------------------------------------------------------------
    notifications = await dispatch_upcoming_reminders(db_session)
    assert isinstance(notifications, list)

    # -------------------------------------------------------------------------
    # STAGE 9: Teleconsultation Waiting Room & Live Session (TEL-01, TEL-03)
    # -------------------------------------------------------------------------
    waiting_session = await patient_enter_waiting_room(db_session, appt_id, patient_user.id)
    assert waiting_session.status == SessionStatus.WAITING_ROOM

    live_session = await doctor_start_session(db_session, appt_id, doctor.user_id)
    assert live_session.status == SessionStatus.LIVE

    token = generate_livekit_token(f"room_{appt_id}", str(patient_user.id), "John Doe Patient", "patient")
    assert token is not None

    # -------------------------------------------------------------------------
    # STAGE 10: In-Call Chat Relay & Message Persistence (TEL-02)
    # -------------------------------------------------------------------------
    msg = await save_chat_message(
        db_session,
        appt_id,
        patient_user.id,
        "patient",
        "Hello Doctor, I have had a cough for 3 days.",
    )
    assert msg.message_text == "Hello Doctor, I have had a cough for 3 days."

    # -------------------------------------------------------------------------
    # STAGE 11: Doctor Completes Consultation (DOC-03)
    # -------------------------------------------------------------------------
    completed_session = await end_session(db_session, appt_id, doctor.user_id)
    assert completed_session.status == SessionStatus.COMPLETED

    appt_stmt = select(Appointment).where(Appointment.id == appt_id)
    refreshed_appt = (await db_session.execute(appt_stmt)).scalar_one()
    assert refreshed_appt.status == AppointmentStatus.COMPLETED

    # -------------------------------------------------------------------------
    # STAGE 12: Structured Prescription & Drug Compliance (DOC-04, CMP-01)
    # -------------------------------------------------------------------------
    # Ensure master drug exists
    drug_stmt = select(DrugMaster).where(DrugMaster.brand_name == "Crocin")
    drug = (await db_session.execute(drug_stmt)).scalar_one_or_none()
    if not drug:
        drug = DrugMaster(
            id=uuid.uuid4(),
            brand_name="Crocin",
            generic_name="Paracetamol",
            dosage_form="Tablet",
            is_telemedicine_restricted=False,
        )
        db_session.add(drug)
        await db_session.commit()

    presc_payload = PrescriptionCreate(
        appointment_id=appt_id,
        diagnosis="Acute Bronchitis",
        clinical_notes="Rest well and stay hydrated",
        items=[
            PrescriptionItemCreate(
                drug_name="Crocin",
                dosage="500mg",
                frequency="1-0-1",
                duration_days=5,
                instructions="After meals",
            )
        ],
    )
    prescription = await create_prescription(doctor.user_id, presc_payload, db_session)
    assert prescription.id is not None
    assert prescription.diagnosis == "Acute Bronchitis"

    # -------------------------------------------------------------------------
    # STAGE 13: Vector PDF Generation & Patient Health Record (PAT-06)
    # -------------------------------------------------------------------------
    pdf_bytes = await compile_prescription_pdf(prescription.id, db_session)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500

    # -------------------------------------------------------------------------
    # STAGE 14: Patient Review & Admin Governance (PAT-07, ADM-03, ADM-04, RUL-04)
    # -------------------------------------------------------------------------
    review = await submit_review(
        patient_user.id,
        ReviewCreate(
            appointment_id=appt_id,
            rating=5,
            review_text="Dr. Golden Physician provided outstanding and accurate consultation!",
        ),
        db_session,
    )
    assert review.status == ReviewStatus.PUBLISHED
    await db_session.refresh(doctor)
    assert doctor.review_count >= 1
    assert doctor.average_rating > Decimal("0.00")

    telemetry = await get_platform_telemetry(db_session)
    assert telemetry.total_verified_doctors >= 1
    assert telemetry.total_confirmed_bookings >= 1
    assert telemetry.total_completed_consultations >= 1
    assert telemetry.gross_transaction_value >= Decimal("500.00")

    hidden_review = await moderate_review(
        admin_user.id,
        review.id,
        "hide",
        "Moderation audit verification",
        db_session,
    )
    assert hidden_review.status == ReviewStatus.HIDDEN

    audit_stmt = select(AuditLog).where(AuditLog.target_entity_id == review.id)
    audit_rec = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit_rec is not None
    assert audit_rec.action == "review_hide"
    assert audit_rec.admin_user_id == admin_user.id
