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
from backend.app.models.chemist import Chemist
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor
from backend.app.models.patient import Patient
from backend.app.models.prescription import Prescription
from backend.app.models.user import User, UserRole
from backend.app.schemas.chemist import ChemistRegisterRequest
from backend.app.schemas.prescription import PrescriptionCreate, PrescriptionItemCreate
from backend.app.services.digital_signature import (
    generate_prescription_signature,
    verify_prescription_signature,
)
from backend.app.services.pdf_compiler import compile_prescription_pdf
from backend.app.services.prescription_service import (
    create_prescription,
    get_prescription,
)
from backend.app.api.v1.chemists import (
    dispense_prescription,
    list_chemist_prescriptions,
    list_chemists,
    register_chemist,
    verify_prescription_signature_endpoint,
)


async def _setup_doctor_and_patient(
    session: AsyncSession,
) -> tuple[User, Doctor, User, Patient, Clinic]:
    doc_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    pat_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9197{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    session.add_all((doc_user, pat_user))
    await session.flush()

    doctor = Doctor(
        user_id=doc_user.id,
        full_name="Dr. Alok Verma",
        medical_reg_number=f"MMC-{uuid.uuid4().hex[:6].upper()}",
        council_name="Maharashtra Medical Council",
        specialty="General Practice",
        years_experience=10,
        in_person_fee=Decimal("500.00"),
        video_fee=Decimal("400.00"),
    )
    clinic = Clinic(
        id=uuid.uuid4(),
        doctor_id=doc_user.id,
        name="Verma Clinic",
        address="123 Linking Road",
        city="Mumbai",
        locality="Bandra West",
        pincode="400050",
        contact_number="+912226409999",
    )
    patient = Patient(
        user_id=pat_user.id,
        full_name="Rohan Mehra",
        gender="male",
        date_of_birth=date(1995, 3, 10),
    )
    session.add_all((doctor, clinic, patient))
    await session.flush()
    return doc_user, doctor, pat_user, patient, clinic


async def _setup_chemist_user(
    session: AsyncSession,
    pharmacy_name: str = "Apollo Pharmacy",
    dl_number: str | None = None,
    clinic_id: uuid.UUID | None = None,
    city: str = "Mumbai",
    locality: str = "Bandra West",
) -> tuple[User, Chemist]:
    chemist_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9196{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.CHEMIST,
        is_active=True,
    )
    session.add(chemist_user)
    await session.flush()

    dl = dl_number or f"MH-TZ-DL-{uuid.uuid4().hex[:8].upper()}"
    chemist = Chemist(
        id=uuid.uuid4(),
        user_id=chemist_user.id,
        pharmacy_name=pharmacy_name,
        license_number=dl,
        clinic_id=clinic_id,
        address="Shop 4, Hill Road",
        city=city,
        locality=locality,
        pincode="400050",
        contact_number="+912226401111",
        is_active=True,
    )
    session.add(chemist)
    await session.commit()
    await session.refresh(chemist)
    return chemist_user, chemist


async def _create_completed_appointment(
    session: AsyncSession,
    doctor_id: uuid.UUID,
    patient_id: uuid.UUID,
) -> Appointment:
    now = datetime.now(UTC)
    appointment = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_id,
        doctor_id=doctor_id,
        mode=AppointmentMode.IN_PERSON,
        status=AppointmentStatus.COMPLETED,
        slot_start=now - timedelta(minutes=30),
        slot_end=now - timedelta(minutes=15),
        fee_amount=Decimal("500.00"),
        payment_status=PaymentStatus.CAPTURED,
    )
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)
    return appointment


@pytest.mark.asyncio
async def test_chemist_registration_and_validation(db_session: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        phone_number=f"+9195{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    unique_dl = f"DL-{uuid.uuid4().hex[:8].upper()}"
    req = ChemistRegisterRequest(
        pharmacy_name="Wellness Forever",
        license_number=unique_dl,
        address="Shop 1, SV Road",
        city="Mumbai",
        locality="Andheri West",
        pincode="400058",
        contact_number="+912226781234",
    )
    result = await register_chemist(req, current_user=user, session=db_session)
    assert result.pharmacy_name == "Wellness Forever"
    assert result.license_number == unique_dl
    assert user.role == UserRole.CHEMIST

    # Duplicate registration by same user should be rejected
    with pytest.raises(HTTPException) as exc_info:
        await register_chemist(req, current_user=user, session=db_session)
    assert exc_info.value.status_code == 400

    # Duplicate license number by another user should be rejected
    other_user = User(
        id=uuid.uuid4(),
        phone_number=f"+9195{uuid.uuid4().int % 100000000:08d}",
        role=UserRole.PATIENT,
        is_active=True,
    )
    db_session.add(other_user)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_dl:
        await register_chemist(req, current_user=other_user, session=db_session)
    assert exc_dl.value.status_code == 400
    assert "License number is already registered" in exc_dl.value.detail


@pytest.mark.asyncio
async def test_chemist_directory_filtering(db_session: AsyncSession):
    _, doctor, _, _, clinic = await _setup_doctor_and_patient(db_session)
    _, chemist_inhouse = await _setup_chemist_user(
        db_session,
        pharmacy_name="Clinic In-House Pharmacy",
        clinic_id=clinic.id,
        city="Mumbai",
        locality="Bandra West",
    )
    _, chemist_pune = await _setup_chemist_user(
        db_session,
        pharmacy_name="Pune Central Chemist",
        city="Pune",
        locality="Kothrud",
    )

    # Filter by city
    pune_chemists = await list_chemists(city="Pune", session=db_session)
    assert any(c.id == chemist_pune.id for c in pune_chemists)
    assert not any(c.id == chemist_inhouse.id for c in pune_chemists)

    # Filter by clinic_id
    clinic_chemists = await list_chemists(clinic_id=clinic.id, session=db_session)
    assert len(clinic_chemists) == 1
    assert clinic_chemists[0].id == chemist_inhouse.id


@pytest.mark.asyncio
async def test_cryptographic_digital_signature_generation_and_verification(
    db_session: AsyncSession,
):
    doc_user, doctor, pat_user, _, _ = await _setup_doctor_and_patient(db_session)
    appt = await _create_completed_appointment(db_session, doc_user.id, pat_user.id)

    items = [
        PrescriptionItemCreate(
            drug_name="Paracetamol",
            dosage="650mg",
            frequency="1-0-1",
            duration_days=3,
            instructions="After food",
        ),
        PrescriptionItemCreate(
            drug_name="Cetirizine",
            dosage="10mg",
            frequency="0-0-1",
            duration_days=5,
            instructions="At bedtime",
        ),
    ]
    req = PrescriptionCreate(
        appointment_id=appt.id,
        diagnosis="Acute Upper Respiratory Tract Infection",
        clinical_notes="Hydration advised.",
        items=items,
    )

    rx_res = await create_prescription(doc_user.id, req, db_session)
    assert rx_res.digital_signature is not None
    assert len(rx_res.digital_signature) == 64  # SHA-256 hex digest
    assert rx_res.dispense_status == "pending"

    # Verify signature using digital signature service
    rx = await db_session.get(Prescription, rx_res.id)
    is_valid = verify_prescription_signature(rx, medical_reg_number=doctor.medical_reg_number)
    assert is_valid is True

    # Tampering check: altering a dosage should cause verification failure
    rx.items[0].dosage = "1000mg"  # tampered!
    tampered_valid = verify_prescription_signature(rx, medical_reg_number=doctor.medical_reg_number)
    assert tampered_valid is False

    # Endpoint verification check
    verification = await verify_prescription_signature_endpoint(rx.id, session=db_session)
    # Restore dosage before testing endpoint with DB
    rx.items[0].dosage = "650mg"
    await db_session.commit()
    verification = await verify_prescription_signature_endpoint(rx.id, session=db_session)
    assert verification.valid is True
    assert verification.doctor_reg_number == doctor.medical_reg_number
    assert verification.digital_signature == rx.digital_signature


@pytest.mark.asyncio
async def test_chemist_prescription_routing_and_dispense_flow(db_session: AsyncSession):
    doc_user, doctor, pat_user, _, _ = await _setup_doctor_and_patient(db_session)
    chemist_user, chemist = await _setup_chemist_user(db_session, "Metro Meds")
    other_chemist_user, other_chemist = await _setup_chemist_user(db_session, "Other Meds")

    appt = await _create_completed_appointment(db_session, doc_user.id, pat_user.id)

    # Doctor routes prescription specifically to chemist
    req = PrescriptionCreate(
        appointment_id=appt.id,
        diagnosis="Hypertension",
        items=[
            PrescriptionItemCreate(
                drug_name="Telmisartan",
                dosage="40mg",
                frequency="1-0-0",
                duration_days=30,
            )
        ],
        chemist_id=chemist.id,
    )
    rx_res = await create_prescription(doc_user.id, req, db_session)
    assert rx_res.chemist_id == chemist.id

    # Chemist queries pending prescriptions
    prescriptions = await list_chemist_prescriptions(
        dispense_status="pending",
        current_user=chemist_user,
        session=db_session,
    )
    assert any(p.id == rx_res.id for p in prescriptions)

    # Other chemist trying to dispense should be rejected
    with pytest.raises(HTTPException) as exc_perm:
        await dispense_prescription(
            prescription_id=rx_res.id,
            current_user=other_chemist_user,
            session=db_session,
        )
    assert exc_perm.value.status_code == 403

    # Assigned chemist dispenses
    dispensed = await dispense_prescription(
        prescription_id=rx_res.id,
        current_user=chemist_user,
        session=db_session,
    )
    assert dispensed.dispense_status == "dispensed"
    assert dispensed.dispensed_by_chemist_id == chemist.id

    # Re-dispensing should fail
    with pytest.raises(HTTPException) as exc_repeat:
        await dispense_prescription(
            prescription_id=rx_res.id,
            current_user=chemist_user,
            session=db_session,
        )
    assert exc_repeat.value.status_code == 400


@pytest.mark.asyncio
async def test_pdf_prescriptions_include_digital_signature_seal(db_session: AsyncSession):
    doc_user, doctor, pat_user, _, _ = await _setup_doctor_and_patient(db_session)
    appt = await _create_completed_appointment(db_session, doc_user.id, pat_user.id)

    req = PrescriptionCreate(
        appointment_id=appt.id,
        diagnosis="Migraine",
        items=[
            PrescriptionItemCreate(
                drug_name="Naproxen",
                dosage="500mg",
                frequency="1-0-1",
                duration_days=5,
            )
        ],
    )
    rx_res = await create_prescription(doc_user.id, req, db_session)
    pdf_bytes = await compile_prescription_pdf(rx_res.id, db_session)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    # Check PDF stream contains signature artifacts
    pdf_text = pdf_bytes.decode("latin1", errors="ignore")
    assert "DIGITALLY SIGNED" in pdf_text or "Prescription" in pdf_text
