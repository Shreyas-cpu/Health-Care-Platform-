import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import require_verification_reviewer
from backend.app.core.database import get_db
from backend.app.models.review import ReviewStatus
from backend.app.models.user import User
from backend.app.schemas.review import ReviewModerationAction, ReviewRead
from backend.app.services.review_service import list_reviews_for_moderation, moderate_review
router = APIRouter(prefix="/admin/moderation", tags=["Admin Moderation"])

@router.get("/reviews", response_model=list[ReviewRead])
async def moderation_reviews(status: ReviewStatus | None = None, _: User = Depends(require_verification_reviewer), session: AsyncSession = Depends(get_db)):
    return await list_reviews_for_moderation(status, session)

@router.post("/reviews/{review_id}/action", response_model=ReviewRead)
async def moderation_action(review_id: uuid.UUID, payload: ReviewModerationAction, current_user: User = Depends(require_verification_reviewer), session: AsyncSession = Depends(get_db)):
    return await moderate_review(current_user.id, review_id, payload.action, payload.reason_text, session)
