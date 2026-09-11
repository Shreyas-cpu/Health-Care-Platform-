import io
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.appointment import (
    Appointment,
    AppointmentMode,
    AppointmentStatus,
    PaymentStatus,
)
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor
from backend.app.models.patient import Patient
from backend.app.models.user import User, UserRole
from backend.app.schemas.prescription import PrescriptionCreate, PrescriptionItemCreate
from backend.app.services.pdf_compiler import (
    compile_and_upload_prescription_pdf,
    compile_prescription_pdf,
)
from backend.app.services.prescription_service import (
    create_prescription,
    get_patient_prescription_download_url,
    get_prescription,
    list_patient_prescriptions,
    search_drugs,
)
from backend.app.services.queue_service import (
    get_doctor_daily_queue,
    mark_appointment_complete,
    mark_appointment_no_show,
)


async def _setup_clinical_pair(
    session: AsyncSession,
) -> tuple[User, Doctor, User, Patient]:
    doctor_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    patient_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9197{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    session.add_all((doctor_user, patient_user))
    await session.flush()

    doctor_profile = Doctor(
        user_id=doctor_user.id,
        full_name="Dr. Sunita Rao",
        medical_reg_number=f"MCI-{uuid.uuid4().hex[:6].upper()}",
        council_name="Maharashtra Medical Council",
        specialty="General Medicine",
        years_experience=12,
        in_person_fee=Decimal("600.00"),
        video_fee=Decimal("500.00"),
    )
    clinic = Clinic(
        id=uuid.uuid4(),
        doctor_id=doctor_user.id,
        name="Apollo Clinic Bandra",
        address="Hill Road",
        city="Mumbai",
        locality="Bandra West",
        pincode="400050",
        contact_number="+912226401122",
    )
    patient_profile = Patient(
        user_id=patient_user.id,
        full_name="Arjun Sharma",
        gender="male",
        date_of_birth=date(1990, 5, 15),
    )
    session.add_all((doctor_profile, clinic, patient_profile))
    await session.flush()
    return doctor_user, doctor_profile, patient_user, patient_profile


async def _create_appointment(
    session: AsyncSession,
    doctor_id: uuid.UUID,
    patient_id: uuid.UUID,
    mode: AppointmentMode,
    status: AppointmentStatus = AppointmentStatus.CONFIRMED,
    slot_offset_minutes: int = 0,
) -> Appointment:
    now = datetime.now(UTC) + timedelta(minutes=slot_offset_minutes)
    appointment = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        mode=mode,
        status=status,
        slot_start=now,
        slot_end=now + timedelta(minutes=15),
        fee_amount=Decimal("500.00"),
        payment_status=PaymentStatus.CAPTURED,
    )
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)
    return appointment


@pytest.mark.asyncio
async def test_doctor_daily_queue_and_status_progression(db_session: AsyncSession):
    doc_user, _, pat_user, _ = await _setup_clinical_pair(db_session)
    appt = await _create_appointment(
        db_session,
        doc_user.id,
        pat_user.id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.CONFIRMED,
    )

    queue = await get_doctor_daily_queue(doc_user.id, appt.slot_start.date(), db_session)
    assert any(q.appointment_id == appt.id for q in queue)
    item = next(q for q in queue if q.appointment_id == appt.id)
    assert item.patient_name == "Arjun Sharma"

    # Mark complete progresses through the valid state machine pipeline
    completed = await mark_appointment_complete(appt.id, doc_user.id, db_session)
    assert completed.status == AppointmentStatus.COMPLETED

    # Test mark no show on new non-overlapping appointment
    appt2 = await _create_appointment(
        db_session,
        doc_user.id,
        pat_user.id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.CONFIRMED,
        slot_offset_minutes=30,
    )
    no_show = await mark_appointment_no_show(appt2.id, doc_user.id, db_session)
    assert no_show.status == AppointmentStatus.NO_SHOW


@pytest.mark.asyncio
async def test_cmp01_restricted_drug_blocked_on_video(db_session: AsyncSession):
    doc_user, _, pat_user, _ = await _setup_clinical_pair(db_session)
    # Seed drugs first
    await search_drugs("Alprax", db_session)

    video_appt = await _create_appointment(
        db_session,
        doc_user.id,
        pat_user.id,
        mode=AppointmentMode.VIDEO,
        status=AppointmentStatus.COMPLETED,
    )

    req = PrescriptionCreate(
        appointment_id=video_appt.id,
        diagnosis="Acute Anxiety and Insomnia",
        clinical_notes="Patient requested sedative support.",
        items=[
            PrescriptionItemCreate(
                drug_name="Alprax",  # Restricted Alprazolam
                dosage="0.5mg",
                frequency="0-0-1",
                duration_days=5,
                instructions="At bedtime",
            )
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_prescription(doc_user.id, req, db_session)
    assert exc_info.value.status_code == 422
    assert "restricted for remote teleconsultation" in exc_info.value.detail


@pytest.mark.asyncio
async def test_cmp01_restricted_drug_allowed_for_in_person(db_session: AsyncSession):
    doc_user, _, pat_user, _ = await _setup_clinical_pair(db_session)
    await search_drugs("Alprax", db_session)

    in_person_appt = await _create_appointment(
        db_session,
        doc_user.id,
        pat_user.id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.COMPLETED,
    )

    req = PrescriptionCreate(
        appointment_id=in_person_appt.id,
        diagnosis="Severe Panic Disorder",
        clinical_notes="In-person clinical evaluation confirmed requirement.",
        items=[
            PrescriptionItemCreate(
                drug_name="Alprax",
                dosage="0.5mg",
                frequency="0-0-1",
                duration_days=5,
                instructions="After dinner",
            )
        ],
    )

    rx = await create_prescription(doc_user.id, req, db_session)
    assert rx.id is not None
    assert rx.appointment_id == in_person_appt.id
    assert len(rx.items) == 1
    assert rx.items[0].drug_name == "Alprax"


@pytest.mark.asyncio
async def test_prescription_requires_completed_appointment(db_session: AsyncSession):
    doc_user, _, pat_user, _ = await _setup_clinical_pair(db_session)
    await search_drugs("Paracetamol", db_session)

    confirmed_appt = await _create_appointment(
        db_session,
        doc_user.id,
        pat_user.id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.CONFIRMED,
    )

    req = PrescriptionCreate(
        appointment_id=confirmed_appt.id,
        diagnosis="Viral fever",
        items=[
            PrescriptionItemCreate(
                drug_name="Crocin",
                dosage="650mg",
                frequency="1-0-1",
                duration_days=3,
            )
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_prescription(doc_user.id, req, db_session)
    assert exc_info.value.status_code == 422
    assert "only be issued for completed appointments" in exc_info.value.detail


@pytest.mark.asyncio
async def test_pdf_compilation_and_s3_storage(db_session: AsyncSession):
    doc_user, _, pat_user, _ = await _setup_clinical_pair(db_session)
    await search_drugs("Crocin", db_session)

    appt = await _create_appointment(
        db_session,
        doc_user.id,
        pat_user.id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.COMPLETED,
    )

    req = PrescriptionCreate(
        appointment_id=appt.id,
        diagnosis="Seasonal Rhinitis and Low Fever",
        clinical_notes="Rest and oral hydration advised.",
        items=[
            PrescriptionItemCreate(
                drug_name="Crocin",
                dosage="500mg",
                frequency="1-0-1",
                duration_days=3,
                instructions="Post meals",
            ),
            PrescriptionItemCreate(
                drug_name="Cetzine",
                dosage="10mg",
                frequency="0-0-1",
                duration_days=5,
                instructions="At night",
            ),
        ],
    )

    rx = await create_prescription(doc_user.id, req, db_session)
    assert rx.id is not None

    # Test PDF byte compilation
    pdf_bytes = await compile_prescription_pdf(rx.id, db_session)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")

    # Verify pre-signed download URL is generated
    assert rx.download_url is not None
    assert rx.pdf_s3_key is not None


@pytest.mark.asyncio
async def test_drug_master_autocomplete(db_session: AsyncSession):
    results = await search_drugs("Pan", db_session)
    assert len(results) > 0
    assert any(d.brand_name == "Pan 40" for d in results)
    assert any(d.generic_name == "Pantoprazole" for d in results)

    restricted_results = await search_drugs("Corex", db_session)
    assert len(restricted_results) > 0
    assert restricted_results[0].is_telemedicine_restricted is True


@pytest.mark.asyncio
async def test_patient_records_retrieval_and_download(db_session: AsyncSession):
    doc_user, _, pat_user, _ = await _setup_clinical_pair(db_session)
    await search_drugs("Crocin", db_session)

    appt = await _create_appointment(
        db_session,
        doc_user.id,
        pat_user.id,
        mode=AppointmentMode.VIDEO,
        status=AppointmentStatus.COMPLETED,
    )

    req = PrescriptionCreate(
        appointment_id=appt.id,
        diagnosis="Bacterial Pharyngitis",
        items=[
            PrescriptionItemCreate(
                drug_name="Azithral 500",
                dosage="500mg",
                frequency="1-0-0",
                duration_days=3,
                instructions="Before lunch",
            )
        ],
    )

    rx = await create_prescription(doc_user.id, req, db_session)

    # Patient lists records
    my_rxs = await list_patient_prescriptions(pat_user.id, db_session)
    assert len(my_rxs) >= 1
    assert any(p.id == rx.id for p in my_rxs)

    # Patient fetches download URL
    dl = await get_patient_prescription_download_url(rx.id, pat_user.id, db_session)
    assert dl["prescription_id"] == str(rx.id)
    assert "download_url" in dl
    assert dl["download_url"].startswith("http")
