import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Set
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.redis import publish_event
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.models.verification import VerificationReview
from backend.app.services.audit import record_audit_log

class InvalidVerificationTransitionError(HTTPException):
    def __init__(self, from_status: VerificationStatus, to_status: VerificationStatus, reason: str = ""):
        detail = f"Illegal verification transition from '{from_status.value}' to '{to_status.value}'."
        if reason:
            detail += f" Reason: {reason}"
        super().__init__(
            status_code=422,
            detail=detail
        )

class VerificationStateMachine:
    """
    PRD Section 2D: 6-state doctor verification pipeline
    1. Submitted
    2. UnderReview
    3. InfoRequested
    4. Verified
    5. Rejected
    6. Suspended
    """
    TRANSITIONS: Dict[VerificationStatus, Set[VerificationStatus]] = {
        VerificationStatus.SUBMITTED: {
            VerificationStatus.UNDER_REVIEW
        },
        VerificationStatus.UNDER_REVIEW: {
            VerificationStatus.INFO_REQUESTED,
            VerificationStatus.VERIFIED,
            VerificationStatus.REJECTED
        },
        VerificationStatus.INFO_REQUESTED: {
            VerificationStatus.SUBMITTED,
            VerificationStatus.UNDER_REVIEW,
            VerificationStatus.REJECTED
        },
        VerificationStatus.VERIFIED: {
            VerificationStatus.SUSPENDED
        },
        VerificationStatus.SUSPENDED: {
            VerificationStatus.UNDER_REVIEW,
            VerificationStatus.VERIFIED
        },
        VerificationStatus.REJECTED: {
            VerificationStatus.UNDER_REVIEW  # Allowed upon formal appeal
        }
    }

    @classmethod
    def can_transition(cls, from_status: VerificationStatus, to_status: VerificationStatus) -> bool:
        allowed = cls.TRANSITIONS.get(from_status, set())
        return to_status in allowed

    @classmethod
    def validate_transition(
        cls,
        from_status: VerificationStatus,
        to_status: VerificationStatus,
        reason_text: Optional[str] = None
    ) -> None:
        if not cls.can_transition(from_status, to_status):
            raise InvalidVerificationTransitionError(from_status, to_status)

        # Rejection or Suspension strictly requires a non-empty reason
        if to_status in (VerificationStatus.REJECTED, VerificationStatus.SUSPENDED):
            if not reason_text or not reason_text.strip():
                raise HTTPException(
                    status_code=422,
                    detail=f"Status transition to '{to_status.value}' strictly requires a non-empty reason."
                )

    async def transition_doctor_status(
        self,
        doctor: Doctor,
        new_status: VerificationStatus,
        admin_user_id: uuid.UUID,
        session: AsyncSession,
        reason_text: Optional[str] = None,
        review_notes: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> VerificationReview:
        """
        Executes atomic transition on doctor verification status.
        Enforces guards, writes review history, and records immutable audit log (RUL-04).
        """
        previous_status = doctor.verification_status
        self.validate_transition(previous_status, new_status, reason_text)

        # Update doctor model
        doctor.verification_status = new_status
        doctor.updated_at = datetime.now(timezone.utc)

        # If taking offline from verified (e.g. suspended, rejected)
        if new_status != VerificationStatus.VERIFIED:
            doctor.listing_online = False
            doctor.video_enabled = False

        # Create review entry
        review = VerificationReview(
            id=uuid.uuid4(),
            doctor_id=doctor.user_id,
            reviewer_admin_id=admin_user_id,
            previous_status=previous_status,
            new_status=new_status,
            reason_text=reason_text.strip() if reason_text else None,
            review_notes=review_notes.strip() if review_notes else None
        )
        session.add(review)

        # RUL-04: Record immutable audit log in the exact same transaction
        audit_action = f"doctor_verification_{new_status.value}"
        audit_reason = reason_text or f"Doctor verification status transitioned to {new_status.value}"
        await record_audit_log(
            admin_user_id=admin_user_id,
            target_entity_type="doctor",
            target_entity_id=doctor.user_id,
            action=audit_action,
            reason=audit_reason,
            session=session,
            previous_state={"status": previous_status.value},
            new_state={"status": new_status.value},
            ip_address=ip_address
        )

        await session.flush()

        # Emit event to Redis Pub/Sub for search cache invalidation (RUL-02)
        try:
            await publish_event(
                "doctor:events",
                "doctor_verification_changed",
                {
                    "doctor_id": str(doctor.user_id),
                    "previous_status": previous_status.value,
                    "new_status": new_status.value,
                    "listing_online": doctor.listing_online
                }
            )
        except Exception as e:
            print(f"[VERIFICATION SERVICE] Warning: Redis event publish failed: {e}")

        return review

verification_state_machine = VerificationStateMachine()
