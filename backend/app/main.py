from contextlib import asynccontextmanager

from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import engine, get_db
from backend.app.models.user import User
from backend.app.schemas.user import (
    OTPRequest,
    OTPVerifyRequest,
    TokenResponse,
    UserRead,
)
from backend.app.services.identity_service import identity_service
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,
    openapi_url="/api/openapi.json",
    docs_url="/docs"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["Health"])
async def health_check(session: AsyncSession = Depends(get_db)):
    await session.execute(text("SELECT 1"))
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "database": "connected"
    }

@app.post(f"{settings.API_V1_STR}/auth/request-otp", tags=["Auth"])
async def request_otp(req: OTPRequest):
    success, message = await identity_service.request_otp(req.phone_number, req.purpose)
    if not success:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)
    return {"success": True, "message": message}

@app.post(f"{settings.API_V1_STR}/auth/verify-otp", response_model=TokenResponse, tags=["Auth"])
async def verify_otp(
    req: OTPVerifyRequest,
    session: AsyncSession = Depends(get_db)
):
    try:
        token_response = await identity_service.verify_otp(
            phone_number=req.phone_number,
            otp_code=req.otp_code,
            role=req.role,
            session=session,
            consent_version=req.consent_version
        )
        return token_response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@app.get(f"{settings.API_V1_STR}/auth/me", response_model=UserRead, tags=["Auth"])
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

# Mount Phase 02 / 03 routers
from backend.app.api.v1.admin_verification import router as admin_verification_router
from backend.app.api.v1.bookings import router as bookings_router
from backend.app.api.v1.cancellations import router as cancellations_router
from backend.app.api.v1.doctor_onboarding import router as doctor_router
from backend.app.api.v1.doctor_profile import router as doctor_profile_router
from backend.app.api.v1.patient_auth import router as patient_auth_router
from backend.app.api.v1.payments import router as payments_router

# Mount Phase 04 routers
from backend.app.api.v1.schedules import router as schedules_router
from backend.app.api.v1.schedules import slots_router
from backend.app.api.v1.search import router as search_router
# Teleconsultation disabled for Clinic-First Architecture pivot
# from backend.app.api.v1.teleconsultation import router as teleconsultation_router
from backend.app.api.v1.reviews import router as reviews_router
from backend.app.api.v1.admin_dashboard import router as admin_dashboard_router
from backend.app.api.v1.admin_moderation import router as admin_moderation_router

# Mount Phase 07 routers
from backend.app.api.v1.appointments import router as appointments_router
from backend.app.api.v1.doctor_queue import router as doctor_queue_router
from backend.app.api.v1.patient_records import router as patient_records_router
from backend.app.api.v1.prescriptions import router as prescriptions_router
from backend.app.api.v1.chemists import router as chemists_router
from backend.app.api.v1.patient_vault import router as patient_vault_router
from backend.app.api.v1.firebase_auth import router as firebase_auth_router

app.include_router(firebase_auth_router, prefix=settings.API_V1_STR)
app.include_router(doctor_router, prefix=settings.API_V1_STR)
app.include_router(admin_verification_router, prefix=settings.API_V1_STR)
app.include_router(patient_auth_router, prefix=settings.API_V1_STR)
app.include_router(doctor_profile_router, prefix=settings.API_V1_STR)
app.include_router(search_router, prefix=settings.API_V1_STR)
# Video teleconsultation endpoint disabled in clinic-first pivot
# app.include_router(teleconsultation_router, prefix=settings.API_V1_STR)
app.include_router(reviews_router, prefix=settings.API_V1_STR)
app.include_router(admin_dashboard_router, prefix=settings.API_V1_STR)
app.include_router(admin_moderation_router, prefix=settings.API_V1_STR)
app.include_router(schedules_router, prefix=settings.API_V1_STR)
app.include_router(slots_router, prefix=settings.API_V1_STR)
app.include_router(bookings_router, prefix=settings.API_V1_STR)
app.include_router(payments_router, prefix=settings.API_V1_STR)
app.include_router(cancellations_router, prefix=settings.API_V1_STR)
app.include_router(appointments_router, prefix=settings.API_V1_STR)
app.include_router(doctor_queue_router, prefix=settings.API_V1_STR)
app.include_router(prescriptions_router, prefix=settings.API_V1_STR)
app.include_router(patient_records_router, prefix=settings.API_V1_STR)
app.include_router(chemists_router, prefix=settings.API_V1_STR)
app.include_router(patient_vault_router, prefix=settings.API_V1_STR)
