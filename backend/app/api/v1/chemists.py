import uuid
from datetime import UTC, datetime

from backend.app.api.deps import get_current_user, require_roles
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.chemist import Chemist
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor
from backend.app.models.prescription import Prescription
from backend.app.models.user import User, UserRole
from backend.app.schemas.chemist import (
    ChemistRegisterRequest,
    ChemistResponse,
    DispensePrescriptionResponse,
    PrescriptionVerificationResponse,
)
from backend.app.schemas.prescription import PrescriptionResponse
from backend.app.services.digital_signature import verify_prescription_signature
from backend.app.services.prescription_service import _to_prescription_response
from backend.app.services.storage import storage_service
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(tags=["Chemists"])


@router.post(
    "/chemists/register",
    response_model=ChemistResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_chemist(
    req: ChemistRegisterRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Register a pharmacy with Drug License (DL) details."""
    # Check if this user already has a registered chemist profile
    existing_user_chemist = await session.execute(
        select(Chemist).where(Chemist.user_id == current_user.id)
    )
    if existing_user_chemist.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A chemist profile already exists for this user account.",
        )

    # Check unique license number
    existing_license = await session.execute(
        select(Chemist).where(Chemist.license_number == req.license_number.strip())
    )
    if existing_license.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Drug License number is already registered.",
        )

    # Check clinic if clinic_id provided
    if req.clinic_id:
        clinic = await session.get(Clinic, req.clinic_id)
        if not clinic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clinic not found.",
            )

    # Update user role to CHEMIST if not already
    if current_user.role != UserRole.CHEMIST:
        current_user.role = UserRole.CHEMIST
        session.add(current_user)

    chemist = Chemist(
        id=uuid.uuid4(),
        user_id=current_user.id,
        pharmacy_name=req.pharmacy_name.strip(),
        license_number=req.license_number.strip(),
        clinic_id=req.clinic_id,
        address=req.address.strip(),
        city=req.city.strip(),
        locality=req.locality.strip(),
        pincode=req.pincode.strip(),
        contact_number=req.contact_number.strip(),
        is_active=True,
    )
    session.add(chemist)
    await session.commit()
    await session.refresh(chemist)
    return chemist


@router.get("/chemists", response_model=list[ChemistResponse])
async def list_chemists(
    city: str | None = None,
    locality: str | None = None,
    clinic_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_db),
):
    """List directory of pharmacies with optional locality/city/clinic filters."""
    query = select(Chemist).where(Chemist.is_active == True)
    if city and isinstance(city, str):
        query = query.where(Chemist.city.ilike(f"%{city.strip()}%"))
    if locality and isinstance(locality, str):
        query = query.where(Chemist.locality.ilike(f"%{locality.strip()}%"))
    if clinic_id:
        query = query.where(Chemist.clinic_id == clinic_id)

    query = query.order_by(Chemist.pharmacy_name.asc())
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/chemist/prescriptions", response_model=list[PrescriptionResponse])
async def list_chemist_prescriptions(
    dispense_status: str | None = None,
    current_user: User = Depends(require_roles(UserRole.CHEMIST)),
    session: AsyncSession = Depends(get_db),
):
    """View digital prescriptions routed to the logged-in chemist."""
    chemist_res = await session.execute(
        select(Chemist).where(Chemist.user_id == current_user.id)
    )
    chemist = chemist_res.scalar_one_or_none()
    if not chemist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chemist profile not found for this account.",
        )

    stmt = (
        select(Prescription)
        .where(Prescription.chemist_id == chemist.id)
        .options(selectinload(Prescription.items))
        .order_by(Prescription.issued_at.desc())
    )
    if dispense_status:
        stmt = stmt.where(Prescription.dispense_status == dispense_status)

    result = await session.execute(stmt)
    prescriptions = result.scalars().all()

    responses: list[PrescriptionResponse] = []
    for rx in prescriptions:
        download_url = None
        if rx.pdf_s3_key:
            download_url = storage_service.generate_presigned_download_url(
                bucket_name=settings.S3_BUCKET_PRESCRIPTIONS,
                s3_key=rx.pdf_s3_key,
            )
        responses.append(_to_prescription_response(rx, download_url=download_url))
    return responses


@router.post(
    "/chemist/prescriptions/{prescription_id}/dispense",
    response_model=DispensePrescriptionResponse,
)
async def dispense_prescription(
    prescription_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.CHEMIST)),
    session: AsyncSession = Depends(get_db),
):
    """Chemist marks prescription as fulfilled / dispensed."""
    chemist_res = await session.execute(
        select(Chemist).where(Chemist.user_id == current_user.id)
    )
    chemist = chemist_res.scalar_one_or_none()
    if not chemist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chemist profile not found for this account.",
        )

    rx = await session.get(Prescription, prescription_id)
    if not rx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found.",
        )

    # If routed to another chemist, disallow dispensing
    if rx.chemist_id is not None and rx.chemist_id != chemist.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This prescription is assigned to a different pharmacy.",
        )

    if rx.dispense_status == "dispensed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prescription was already dispensed at {rx.dispensed_at}.",
        )

    now = datetime.now(UTC)
    rx.dispense_status = "dispensed"
    rx.dispensed_at = now
    rx.dispensed_by_chemist_id = chemist.id
    if rx.chemist_id is None:
        rx.chemist_id = chemist.id

    session.add(rx)
    await session.commit()
    await session.refresh(rx)

    return DispensePrescriptionResponse(
        message="Prescription successfully dispensed.",
        prescription_id=rx.id,
        dispense_status=rx.dispense_status,
        dispensed_at=rx.dispensed_at,
        dispensed_by_chemist_id=chemist.id,
    )


@router.get(
    "/prescriptions/{prescription_id}/verify",
    response_model=PrescriptionVerificationResponse,
)
async def verify_prescription_signature_endpoint(
    prescription_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Public / Chemist endpoint to cryptographically verify digital signature integrity."""
    rx = await session.get(
        Prescription,
        prescription_id,
        options=[selectinload(Prescription.items)],
    )
    if not rx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found.",
        )

    doctor = await session.get(Doctor, rx.doctor_id)
    reg_number = (
        doctor.medical_reg_number
        if doctor and doctor.medical_reg_number
        else "MCI-REG-PROVISIONAL"
    )

    is_valid = verify_prescription_signature(
        prescription=rx,
        medical_reg_number=reg_number,
    )

    return PrescriptionVerificationResponse(
        valid=is_valid,
        prescription_id=rx.id,
        doctor_id=rx.doctor_id,
        patient_id=rx.patient_id,
        appointment_id=rx.appointment_id,
        doctor_reg_number=reg_number,
        issued_at=rx.issued_at,
        digital_signature=rx.digital_signature,
        dispense_status=rx.dispense_status,
        dispensed_at=rx.dispensed_at,
        message="Cryptographic signature verified. Prescription integrity confirmed."
        if is_valid
        else "Signature verification failed: prescription details may have been tampered with.",
    )
