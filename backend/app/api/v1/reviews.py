import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import require_roles
from backend.app.core.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.schemas.review import ReviewCreate, ReviewRead
from backend.app.services.review_service import list_doctor_reviews, submit_review
router = APIRouter(prefix="/reviews", tags=["Reviews"])

@router.post("/", response_model=ReviewRead)
async def create_review(payload: ReviewCreate, current_user: User = Depends(require_roles(UserRole.PATIENT)), session: AsyncSession = Depends(get_db)):
    return await submit_review(current_user.id, payload, session)

@router.get("/doctor/{doctor_id}", response_model=list[ReviewRead])
async def doctor_reviews(doctor_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    return await list_doctor_reviews(doctor_id, session)
