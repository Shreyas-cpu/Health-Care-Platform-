from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import engine, get_db
from backend.app.models.user import User
from backend.app.schemas.user import OTPRequest, OTPVerifyRequest, TokenResponse, UserRead
from backend.app.services.identity_service import identity_service

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

# Mount Phase 02 routers
from backend.app.api.v1.doctor_onboarding import router as doctor_router
from backend.app.api.v1.admin_verification import router as admin_verification_router

app.include_router(doctor_router, prefix=settings.API_V1_STR)
app.include_router(admin_verification_router, prefix=settings.API_V1_STR)
