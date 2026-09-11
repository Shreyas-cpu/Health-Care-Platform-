import uuid

from backend.app.api.deps import require_verification_reviewer
from backend.app.core.database import get_db
from backend.app.models.chemist import Chemist
from backend.app.models.review import ReviewStatus
from backend.app.models.user import User
from backend.app.schemas.admin import ChemistStatusUpdateAction
from backend.app.schemas.chemist import ChemistResponse
from backend.app.schemas.review import ReviewModerationAction, ReviewRead
from backend.app.services.audit import record_audit_log
from backend.app.services.review_service import (
    list_reviews_for_moderation,
    moderate_review,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/admin/moderation", tags=["Admin Moderation"])


@router.get("/reviews", response_model=list[ReviewRead])
async def moderation_reviews(
    status: ReviewStatus | None = None,
    _: User = Depends(require_verification_reviewer),
    session: AsyncSession = Depends(get_db),
):
    return await list_reviews_for_moderation(status, session)


@router.post("/reviews/{review_id}/action", response_model=ReviewRead)
async def moderation_action(
    review_id: uuid.UUID,
    payload: ReviewModerationAction,
    current_user: User = Depends(require_verification_reviewer),
    session: AsyncSession = Depends(get_db),
):
    return await moderate_review(
        current_user.id, review_id, payload.action, payload.reason_text, session
    )


@router.get("/chemists", response_model=list[ChemistResponse])
async def list_chemists_for_moderation(
    current_user: User = Depends(require_verification_reviewer),
    session: AsyncSession = Depends(get_db),
) -> list[Chemist]:
    """List all registered pharmacies, DL numbers, clinic affiliations, and active statuses."""
    stmt = select(Chemist).order_by(Chemist.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("/chemists/{chemist_id}/status", response_model=ChemistResponse)
async def update_chemist_status(
    chemist_id: uuid.UUID,
    payload: ChemistStatusUpdateAction,
    current_user: User = Depends(require_verification_reviewer),
    session: AsyncSession = Depends(get_db),
) -> Chemist:
    """Toggle or update chemist status with mandatory RUL-04 audit logging."""
    chemist = (
        await session.execute(select(Chemist).where(Chemist.id == chemist_id))
    ).scalar_one_or_none()
    if not chemist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chemist not found.",
        )

    action_lower = payload.action.strip().lower()
    mapping = {
        "activate": True,
        "suspend": False,
        "deactivate": False,
    }
    if action_lower not in mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported status action '{payload.action}'. Supported actions: activate, suspend, deactivate.",
        )

    if not payload.reason_text or not payload.reason_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason text is mandatory for chemist status change.",
        )

    target_active = mapping[action_lower]
    previous_active = chemist.is_active
    previous_status_str = "active" if previous_active else "suspended"
    new_status_str = "active" if target_active else "suspended"

    # Enforce RUL-04: write immutable audit log within the same database transaction
    await record_audit_log(
        admin_user_id=current_user.id,
        target_entity_type="chemist",
        target_entity_id=chemist.id,
        action=f"chemist_{action_lower}",
        reason=payload.reason_text.strip(),
        session=session,
        previous_state={"status": previous_status_str, "is_active": previous_active},
        new_state={"status": new_status_str, "is_active": target_active},
    )

    chemist.is_active = target_active
    session.add(chemist)
    await session.commit()
    await session.refresh(chemist)
    return chemist
