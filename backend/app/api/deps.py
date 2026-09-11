import uuid

from backend.app.core.database import get_db
from backend.app.core.security import decode_token
from backend.app.models.user import User, UserRole
from backend.app.services.firebase_auth import verify_firebase_id_token
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

security_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    user: User | None = None

    # 1. First attempt platform JWT decode
    try:
        payload = decode_token(token)
        user_id_str = payload.get("sub")
        if user_id_str:
            user_id = uuid.UUID(user_id_str)
            stmt = select(User).where(User.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
    except Exception:
        user = None

    # 2. Fallback to direct Firebase ID token verification
    if not user:
        try:
            fb_payload = verify_firebase_id_token(token)
            uid = fb_payload.get("uid") or fb_payload.get("sub")
            if uid:
                stmt = select(User).where(User.firebase_uid == uid)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
        except Exception:
            user = None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is deactivated"
        )
    return user


def require_roles(*allowed_roles: UserRole):
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{user.role.value}'",
            )
        return user

    return role_checker


require_super_admin = require_roles(UserRole.SUPER_ADMIN)
require_verification_reviewer = require_roles(
    UserRole.VERIFICATION_REVIEWER, UserRole.SUPER_ADMIN
)
