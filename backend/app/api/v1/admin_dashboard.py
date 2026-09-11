from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import require_super_admin
from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.admin import PlatformTelemetryResponse
from backend.app.services.admin_analytics import get_platform_telemetry
router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])

@router.get("/telemetry", response_model=PlatformTelemetryResponse)
async def telemetry(_: User = Depends(require_super_admin), session: AsyncSession = Depends(get_db)):
    return await get_platform_telemetry(session)
