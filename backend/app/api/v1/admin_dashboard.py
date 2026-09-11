from datetime import UTC, datetime

from backend.app.api.deps import require_super_admin
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.admin import (
    PlatformTelemetryResponse,
    ReminderDispatchResponse,
)
from backend.app.services.admin_analytics import get_platform_telemetry
from backend.app.services.reminder_service import dispatch_upcoming_reminders
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])


@router.get("/telemetry", response_model=PlatformTelemetryResponse)
async def telemetry(
    _: User = Depends(require_super_admin), session: AsyncSession = Depends(get_db)
):
    return await get_platform_telemetry(session)


@router.post("/dispatch-reminders", response_model=ReminderDispatchResponse)
async def dispatch_reminders(
    _: User = Depends(require_super_admin),
    session: AsyncSession = Depends(get_db),
):
    now = datetime.now(UTC)
    notifications = await dispatch_upcoming_reminders(session)
    return {
        "dispatched_count": len(notifications),
        "timestamp": now.isoformat(),
    }
