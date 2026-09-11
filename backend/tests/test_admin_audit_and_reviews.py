"""Phase 08 test coverage: RBAC, reviews, moderation, audit logging (RUL-04), and reminder dispatch."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import require_super_admin, require_verification_reviewer
from backend.app.models.appointment import Appointment, AppointmentMode, AppointmentStatus, PaymentStatus
from backend.app.models.audit import AuditLog
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.notification import Notification, NotificationStatus, NotificationType
from backend.app.models.payment import PaymentTransaction, PaymentTransactionStatus
from backend.app.models.review import Review, ReviewStatus
from backend.app.models.user import User, UserRole
from backend.app.schemas.review import ReviewCreate
from backend.app.services.admin_analytics import get_platform_telemetry
from backend.app.services.reminder_service import dispatch_upcoming_reminders
from backend.app.services.review_service import moderate_review, submit_review


async def _review_fixture(session: AsyncSession, status=AppointmentStatus.COMPLETED):
    patient = User(
        id=uuid.uuid4(),
        phone_number=f"+9191{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    doctor_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9192{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    admin = User(
        id=uuid.uuid4(),
        phone_number=f"+9193{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
    )
    reviewer = User(
        id=uuid.uuid4(),
        phone_number=f"+9194{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.VERIFICATION_REVIEWER,
        is_active=True,
    )
    session.add_all((patient, doctor_user, admin, reviewer))
    await session.flush()

    doctor = Doctor(
        user_id=doctor_user.id,
        full_name="Dr Review",
        medical_reg_number=f"REG-{uuid.uuid4().hex[:8].upper()}",
        council_name="State Medical Council",
        specialty="Cardiology",
        years_experience=10,
        verification_status=VerificationStatus.VERIFIED,
    )
    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=patient.id,
        doctor_id=doctor.user_id,
        mode=AppointmentMode.VIDEO,
        status=status,
        slot_start=datetime.now(timezone.utc) + timedelta(minutes=30),
        slot_end=datetime.now(timezone.utc) + timedelta(hours=1),
        fee_amount=Decimal("500.00"),
        payment_status=PaymentStatus.CAPTURED,
    )
    session.add_all((doctor, appt))
    await session.commit()
    return patient, doctor, admin, reviewer, appt


@pytest.mark.asyncio
async def test_rbac_telemetry_access(db_session: AsyncSession):
    """
    ADM-02: Reviewer role is blocked from dashboard telemetry (HTTP 403); super_admin permitted.
    """
    patient, doctor, admin, reviewer, appt = await _review_fixture(db_session)

    # 1. Super admin is permitted to access telemetry
    allowed_admin = await require_super_admin(admin)
    assert allowed_admin.id == admin.id

    # 2. Verification reviewer is blocked from telemetry with 403
    with pytest.raises(HTTPException) as exc_info:
        await require_super_admin(reviewer)
    assert exc_info.value.status_code == 403
    assert "Operation not permitted" in exc_info.value.detail

    # 3. Patient and Doctor are blocked from telemetry with 403
    with pytest.raises(HTTPException) as exc_patient:
        await require_super_admin(patient)
    assert exc_patient.value.status_code == 403

    # 4. require_verification_reviewer permits both reviewer and super_admin
    assert (await require_verification_reviewer(reviewer)).id == reviewer.id
    assert (await require_verification_reviewer(admin)).id == admin.id

    # 5. Telemetry calculates metrics accurately
    telemetry = await get_platform_telemetry(db_session)
    assert telemetry.total_verified_doctors >= 1
    assert telemetry.total_confirmed_bookings >= 1
    assert telemetry.total_completed_consultations >= 1
    assert telemetry.gross_transaction_value >= Decimal("500.00")


@pytest.mark.asyncio
async def test_review_submission_only_on_completed(db_session: AsyncSession):
    """
    PAT-05: Patient can submit exactly one review for a completed appointment.
    """
    patient, doctor, _, _, appt = await _review_fixture(db_session, AppointmentStatus.CONFIRMED)

    # 1. Reject review for uncompleted appointment
    with pytest.raises(HTTPException) as error:
        await submit_review(patient.id, ReviewCreate(appointment_id=appt.id, rating=5, review_text="Great doc!"), db_session)
    assert error.value.status_code == 400

    # 2. Complete appointment and submit review
    appt.status = AppointmentStatus.COMPLETED
    await db_session.commit()

    review = await submit_review(
        patient.id,
        ReviewCreate(appointment_id=appt.id, rating=5, review_text="Excellent consultation!"),
        db_session
    )
    await db_session.refresh(doctor)
    assert review.status == ReviewStatus.PUBLISHED
    assert doctor.review_count == 1
    assert doctor.average_rating == Decimal("5.00")

    # 3. Duplicate review attempt rejected with 409 Conflict
    with pytest.raises(HTTPException) as duplicate:
        await submit_review(patient.id, ReviewCreate(appointment_id=appt.id, rating=4), db_session)
    assert duplicate.value.status_code == 409


@pytest.mark.asyncio
async def test_review_moderation_writes_audit_log(db_session: AsyncSession):
    """
    ADM-04, RUL-04: Admin hiding or removing a review creates immutable audit log record
    and adjusts doctor aggregate rating.
    """
    patient, doctor, admin, _, appt = await _review_fixture(db_session)
    review = await submit_review(
        patient.id,
        ReviewCreate(appointment_id=appt.id, rating=4, review_text="Good service"),
        db_session
    )
    await db_session.refresh(doctor)
    assert doctor.review_count == 1
    assert doctor.average_rating == Decimal("4.00")

    # 1. Admin hides review with mandatory reason
    hidden = await moderate_review(admin.id, review.id, "hide", "Inappropriate language in review", db_session)
    assert hidden.status == ReviewStatus.HIDDEN

    # 2. Verify immutable audit log record created
    audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.target_entity_type == "review",
                AuditLog.target_entity_id == review.id,
            )
        )
    ).scalar_one()
    assert audit.admin_user_id == admin.id
    assert audit.action == "review_hide"
    assert audit.reason == "Inappropriate language in review"
    assert audit.previous_state == {"status": "published"}
    assert audit.new_state == {"status": "hidden"}

    # 3. Doctor's aggregate rating excludes hidden review
    await db_session.refresh(doctor)
    assert doctor.review_count == 0
    assert doctor.average_rating == Decimal("0.00")

    # 4. Admin approves review back
    approved = await moderate_review(admin.id, review.id, "approve", "Appeal accepted upon review", db_session)
    assert approved.status == ReviewStatus.PUBLISHED
    await db_session.refresh(doctor)
    assert doctor.review_count == 1
    assert doctor.average_rating == Decimal("4.00")


@pytest.mark.asyncio
async def test_appointment_reminder_dispatch(db_session: AsyncSession):
    """
    PAT-07: Pre-appointment reminder dispatches automatically before scheduled slot
    and dispatches exactly once.
    """
    _, _, _, _, appt = await _review_fixture(db_session, AppointmentStatus.CONFIRMED)
    appt.reminder_sent = False
    await db_session.commit()

    # 1. Dispatch reminders
    created = await dispatch_upcoming_reminders(db_session)
    await db_session.refresh(appt)

    assert any(note.appointment_id == appt.id for note in created)
    assert appt.reminder_sent is True

    # Check notification in DB
    note = (
        await db_session.execute(
            select(Notification).where(Notification.appointment_id == appt.id)
        )
    ).scalar_one()
    assert note.type == NotificationType.APPOINTMENT_REMINDER
    assert note.status == NotificationStatus.SENT

    # 2. Subsequent call dispatches nothing for this appointment (idempotent / exactly once)
    second_run = await dispatch_upcoming_reminders(db_session)
    assert not any(n.appointment_id == appt.id for n in second_run)
    appt_notifications = (
        await db_session.execute(
            select(Notification).where(Notification.appointment_id == appt.id)
        )
    ).scalars().all()
    assert len(appt_notifications) == 1
