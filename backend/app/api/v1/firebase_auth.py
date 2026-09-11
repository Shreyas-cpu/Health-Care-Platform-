from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.security import create_access_token
from backend.app.models.user import User
from backend.app.schemas.firebase_auth import (
    FirebaseBindPhoneRequest,
    FirebaseLoginRequest,
    FirebaseLoginResponse,
    FirebaseVerifyTokenRequest,
    FirebaseVerifyTokenResponse,
)
from backend.app.services.firebase_auth import (
    sync_firebase_user,
    verify_firebase_id_token,
)
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth/firebase", tags=["Firebase Authentication"])


@router.post("/login", response_model=FirebaseLoginResponse)
async def firebase_login(
    req: FirebaseLoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """
    Exchanges a Firebase ID Token (JWT) from Firebase Phone Auth or Google Sign-In
    for a platform session access token, auto-provisioning the User profile and
    DPDP consent record on first login.
    """
    payload = verify_firebase_id_token(req.id_token)
    client_ip = request.client.host if request.client else None

    user, is_new_user = await sync_firebase_user(
        token_payload=payload,
        role=req.role,
        session=session,
        consent_version=req.consent_version,
        client_ip=client_ip,
        full_name=req.full_name,
    )

    access_token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
        extra_claims={
            "firebase_uid": user.firebase_uid,
            "phone": user.phone_number,
            "email": user.email,
        },
    )

    return FirebaseLoginResponse(
        access_token=access_token,
        token_type="bearer",
        firebase_uid=user.firebase_uid,
        user_id=user.id,
        role=user.role,
        phone_number=user.phone_number,
        email=user.email,
        is_new_user=is_new_user,
    )


@router.post("/verify", response_model=FirebaseVerifyTokenResponse)
async def verify_token(req: FirebaseVerifyTokenRequest):
    """Verifies a Firebase ID token and inspects its decoded identity claims."""
    payload = verify_firebase_id_token(req.id_token)
    return FirebaseVerifyTokenResponse(
        valid=True,
        uid=payload.get("uid") or payload.get("sub", ""),
        email=payload.get("email"),
        phone_number=payload.get("phone_number"),
        name=payload.get("name"),
    )


@router.post("/bind-phone")
async def bind_phone(
    req: FirebaseBindPhoneRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Binds or updates a phone number on the currently authenticated user profile."""
    current_user.phone_number = req.phone_number
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return {
        "success": True,
        "message": f"Phone number successfully updated to {req.phone_number}",
        "phone_number": current_user.phone_number,
    }


@router.get("/me")
async def get_firebase_profile(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's Firebase identity profile."""
    return {
        "user_id": current_user.id,
        "firebase_uid": current_user.firebase_uid,
        "phone_number": current_user.phone_number,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }
