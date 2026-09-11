import uuid
from datetime import date

from backend.app.api.deps import require_roles
from backend.app.core.database import get_db
from backend.app.models.doctor import Doctor
from backend.app.models.schedule import DoctorAvailability, DoctorLeave
from backend.app.models.user import User, UserRole
from backend.app.schemas.schedule import (
    AvailabilityCreate,
    AvailabilityResponse,
    LeaveCreate,
    LeaveResponse,
    SlotResponse,
)
from backend.app.services.schedule_engine import generate_slots
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/schedules", tags=["Schedules & Availability"])
slots_router = APIRouter(prefix="/doctors", tags=["Schedules & Availability"])


@router.post(
    "/availability",
    response_model=AvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_availability(
    data: AvailabilityCreate,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db),
):
    doctor = (
        await session.execute(select(Doctor).where(Doctor.user_id == current_user.id))
    ).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found. Register before setting availability.",
        )

    if data.start_time >= data.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be before end_time",
        )

    availability = DoctorAvailability(
        id=uuid.uuid4(),
        doctor_id=current_user.id,
        clinic_id=data.clinic_id,
        day_of_week=data.day_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
        slot_duration_minutes=data.slot_duration_minutes,
        buffer_minutes=data.buffer_minutes,
        mode=data.mode,
        is_active=True,
    )
    session.add(availability)
    await session.commit()
    await session.refresh(availability)
    return availability


@router.get("/availability", response_model=list[AvailabilityResponse])
async def list_availability(
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(DoctorAvailability)
        .where(DoctorAvailability.doctor_id == current_user.id)
        .order_by(DoctorAvailability.day_of_week, DoctorAvailability.start_time)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return rows


@router.post("/leaves", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
async def create_leave(
    data: LeaveCreate,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db),
):
    doctor = (
        await session.execute(select(Doctor).where(Doctor.user_id == current_user.id))
    ).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found.",
        )

    leave = DoctorLeave(
        id=uuid.uuid4(),
        doctor_id=current_user.id,
        leave_date=data.leave_date,
        reason=data.reason,
    )
    session.add(leave)
    await session.commit()
    await session.refresh(leave)
    return leave


@slots_router.get("/{doctor_id}/slots", response_model=list[SlotResponse])
async def get_doctor_slots(
    doctor_id: uuid.UUID,
    date: date = Query(..., description="Date to query slots for (YYYY-MM-DD)"),
    mode: str | None = Query(None, pattern="^(in_person|video)$"),
    session: AsyncSession = Depends(get_db),
):
    return await generate_slots(
        doctor_id=doctor_id,
        query_date=date,
        mode=mode,
        session=session,
    )
