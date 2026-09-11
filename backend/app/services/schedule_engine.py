import uuid
from datetime import UTC, date, datetime, timedelta

from backend.app.core.redis import get_redis_client, lock_manager
from backend.app.models.appointment import Appointment, AppointmentStatus
from backend.app.models.doctor import Doctor
from backend.app.models.schedule import DoctorAvailability, DoctorLeave
from backend.app.schemas.schedule import SlotResponse
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession


async def generate_slots(
    doctor_id: uuid.UUID,
    query_date: date,
    mode: str | None = None,
    session: AsyncSession = None,
) -> list[SlotResponse]:
    """
    Generate available discrete slots for a doctor on a given date.

    Filters out leave days, already-booked appointments, and Redis-locked holds.
    """
    if session is None:
        raise ValueError("session is required")

    # 1. Leave day blocks all inventory
    leave_stmt = select(DoctorLeave).where(
        DoctorLeave.doctor_id == doctor_id,
        DoctorLeave.leave_date == query_date,
    )
    leave = (await session.execute(leave_stmt)).scalar_one_or_none()
    if leave is not None:
        return []

    # 2. Active availability for this weekday (Python weekday: 0=Mon .. 6=Sun)
    day_of_week = query_date.weekday()
    avail_stmt = select(DoctorAvailability).where(
        DoctorAvailability.doctor_id == doctor_id,
        DoctorAvailability.day_of_week == day_of_week,
        DoctorAvailability.is_active.is_(True),
    )
    windows = list((await session.execute(avail_stmt)).scalars().all())
    if not windows:
        return []

    # 3. Doctor fees
    doctor = (
        await session.execute(select(Doctor).where(Doctor.user_id == doctor_id))
    ).scalar_one_or_none()
    if doctor is None:
        return []

    in_person_fee = doctor.in_person_fee
    video_fee = doctor.video_fee

    # 4. Generate candidate slot intervals
    candidates: list[SlotResponse] = []
    for window in windows:
        slot_modes = _modes_for_window(window.mode, mode)
        if not slot_modes:
            continue

        current = datetime.combine(query_date, window.start_time, tzinfo=UTC)
        window_end = datetime.combine(query_date, window.end_time, tzinfo=UTC)
        duration = timedelta(minutes=window.slot_duration_minutes)
        step = timedelta(minutes=window.slot_duration_minutes + window.buffer_minutes)

        while current + duration <= window_end:
            for slot_mode in slot_modes:
                fee = video_fee if slot_mode == "video" else in_person_fee
                candidates.append(
                    SlotResponse(
                        start_time=current,
                        end_time=current + duration,
                        mode=slot_mode,
                        clinic_id=window.clinic_id,
                        fee_amount=fee,
                        is_available=True,
                    )
                )
            current = current + step

    if not candidates:
        return []

    # 5. Active appointments that block inventory
    day_start = datetime.combine(query_date, datetime.min.time(), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    blocked_statuses = {AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW}
    appt_stmt = select(Appointment).where(
        and_(
            Appointment.doctor_id == doctor_id,
            Appointment.slot_start >= day_start,
            Appointment.slot_start < day_end,
            Appointment.status.notin_(list(blocked_statuses)),
        )
    )
    active_appts = list((await session.execute(appt_stmt)).scalars().all())

    def _is_booked(slot: SlotResponse) -> bool:
        for appt in active_appts:
            # Overlap check on same mode (or any active hold)
            if appt.slot_start < slot.end_time and appt.slot_end > slot.start_time:
                return True
        return False

    # 6 & 7. Filter booked and Redis-locked slots
    available: list[SlotResponse] = []
    redis = get_redis_client()
    try:
        for slot in candidates:
            if _is_booked(slot):
                continue
            lock_key = lock_manager.format_slot_key(
                str(doctor_id), slot.start_time.isoformat()
            )
            locked = await redis.exists(lock_key)
            if locked:
                continue
            available.append(slot)
    finally:
        await redis.aclose()

    return available


def _modes_for_window(window_mode: str, requested_mode: str | None) -> list[str]:
    available = ["in_person", "video"] if window_mode == "both" else [window_mode]
    if requested_mode:
        return [requested_mode] if requested_mode in available else []
    return available
