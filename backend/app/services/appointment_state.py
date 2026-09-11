from datetime import UTC, datetime
from typing import Any

from backend.app.core.redis import publish_event
from backend.app.models.appointment import Appointment, AppointmentStatus
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


class InvalidStateTransitionError(HTTPException):
    def __init__(
        self,
        from_status: AppointmentStatus,
        to_status: AppointmentStatus,
        reason: str = "",
    ):
        detail = f"Illegal appointment transition from '{from_status.value}' to '{to_status.value}'."
        if reason:
            detail += f" Reason: {reason}"
        super().__init__(status_code=422, detail=detail)


class AppointmentStateMachine:
    """
    Implements PRD Section 2A: 8-state appointment lifecycle transition matrix.
    States:
      1. Requested
      2. Confirmed
      3. Rescheduled
      4. CheckedIn
      5. InConsultation
      6. Completed
      7. Cancelled
      8. NoShow
    """

    TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
        AppointmentStatus.REQUESTED: {
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.CANCELLED,
        },
        AppointmentStatus.CONFIRMED: {
            AppointmentStatus.RESCHEDULED,
            AppointmentStatus.CHECKED_IN,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
        },
        AppointmentStatus.RESCHEDULED: {
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.CANCELLED,
        },
        AppointmentStatus.CHECKED_IN: {
            AppointmentStatus.IN_CONSULTATION,
            AppointmentStatus.NO_SHOW,
            AppointmentStatus.CANCELLED,
        },
        AppointmentStatus.IN_CONSULTATION: {
            AppointmentStatus.COMPLETED,
        },
        # Terminal states
        AppointmentStatus.COMPLETED: set(),
        AppointmentStatus.CANCELLED: set(),
        AppointmentStatus.NO_SHOW: set(),
    }

    @classmethod
    def can_transition(
        cls, from_status: AppointmentStatus, to_status: AppointmentStatus
    ) -> bool:
        allowed = cls.TRANSITIONS.get(from_status, set())
        return to_status in allowed

    @classmethod
    def validate_transition(
        cls, from_status: AppointmentStatus, to_status: AppointmentStatus
    ) -> None:
        if not cls.can_transition(from_status, to_status):
            raise InvalidStateTransitionError(from_status, to_status)

    async def transition(
        self,
        appointment: Appointment,
        target_status: AppointmentStatus,
        session: AsyncSession,
        reason: str | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> Appointment:
        """
        Executes an atomic transition on the appointment record.
        Validates transition guards.
        Emits real-time event to Redis Pub/Sub for Node.js WebSocket gateway.
        """
        current_status = appointment.status
        self.validate_transition(current_status, target_status)

        # Transition specific actions
        now = datetime.now(UTC)
        appointment.status = target_status
        appointment.updated_at = now

        if target_status == AppointmentStatus.CANCELLED and reason:
            appointment.cancellation_reason = reason

        await session.flush()

        # Emit event to Redis Pub/Sub for live appointment routing (Section 4)
        event_payload = {
            "appointment_id": str(appointment.id),
            "doctor_id": str(appointment.doctor_id),
            "patient_id": str(appointment.patient_id),
            "previous_status": current_status.value,
            "new_status": target_status.value,
            "timestamp": now.isoformat(),
        }
        if extra_data:
            event_payload.update(extra_data)

        try:
            await publish_event(
                "appointment:events", "appointment_status_changed", event_payload
            )
        except Exception as e:
            # Non-blocking for DB transaction, but logged
            print(f"[STATE MACHINE] Warning: Redis Pub/Sub event publish failed: {e}")

        return appointment


appointment_state_machine = AppointmentStateMachine()
