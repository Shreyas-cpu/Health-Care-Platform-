import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.appointment import Appointment, AppointmentStatus
from backend.app.models.doctor import Doctor
from backend.app.models.review import Review, ReviewStatus
from backend.app.schemas.review import ReviewCreate
from backend.app.services.audit import record_audit_log

async def recalculate_doctor_rating(doctor_id: uuid.UUID, session: AsyncSession) -> None:
    doctor = (await session.execute(select(Doctor).where(Doctor.user_id == doctor_id))).scalar_one()
    count, average = (await session.execute(select(func.count(Review.id), func.avg(Review.rating)).where(Review.doctor_id == doctor_id, Review.status == ReviewStatus.PUBLISHED))).one()
    doctor.review_count = int(count or 0)
    doctor.average_rating = Decimal(str(round(float(average or 0), 2)))
    await session.flush()

async def submit_review(patient_id: uuid.UUID, payload: ReviewCreate, session: AsyncSession) -> Review:
    appointment = (await session.execute(select(Appointment).where(Appointment.id == payload.appointment_id))).scalar_one_or_none()
    if not appointment: raise HTTPException(404, "Appointment not found.")
    if appointment.patient_id != patient_id: raise HTTPException(403, "Only the appointment patient may submit a review.")
    if appointment.status != AppointmentStatus.COMPLETED: raise HTTPException(400, "Reviews are available only after consultation completion.")
    if (await session.execute(select(Review.id).where(Review.appointment_id == appointment.id))).scalar_one_or_none(): raise HTTPException(409, "A review already exists for this appointment.")
    review = Review(appointment_id=appointment.id, doctor_id=appointment.doctor_id, patient_id=patient_id, rating=payload.rating, review_text=payload.review_text, status=ReviewStatus.PUBLISHED)
    session.add(review); await session.flush(); await recalculate_doctor_rating(appointment.doctor_id, session)
    await session.commit(); await session.refresh(review)
    return review

async def moderate_review(admin_user_id: uuid.UUID, review_id: uuid.UUID, action: str, reason_text: str, session: AsyncSession) -> Review:
    review = (await session.execute(select(Review).where(Review.id == review_id))).scalar_one_or_none()
    if not review: raise HTTPException(404, "Review not found.")
    mapping = {"hide": ReviewStatus.HIDDEN, "remove": ReviewStatus.REMOVED, "approve": ReviewStatus.PUBLISHED}
    if action not in mapping: raise HTTPException(400, "Unsupported moderation action.")
    new_status = mapping[action]
    await record_audit_log(admin_user_id=admin_user_id, target_entity_type="review", target_entity_id=review.id, action=f"review_{action.lower()}", reason=reason_text, session=session, previous_state={"status": review.status.value}, new_state={"status": new_status.value})
    review.status = new_status
    await session.flush()
    await recalculate_doctor_rating(review.doctor_id, session)
    await session.commit(); await session.refresh(review)
    return review

async def list_doctor_reviews(doctor_id: uuid.UUID, session: AsyncSession) -> list[Review]:
    return list((await session.execute(select(Review).where(Review.doctor_id == doctor_id, Review.status == ReviewStatus.PUBLISHED).order_by(Review.created_at.desc()))).scalars().all())

async def list_reviews_for_moderation(status_filter: ReviewStatus | None, session: AsyncSession) -> list[Review]:
    query = select(Review).order_by(Review.created_at.desc())
    if status_filter is not None: query = query.where(Review.status == status_filter)
    return list((await session.execute(query)).scalars().all())
