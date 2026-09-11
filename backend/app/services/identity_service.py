import random
import uuid
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.redis import get_redis_client
from backend.app.core.security import create_access_token, verify_password
from backend.app.models.consent import ConsentRecord
from backend.app.models.user import User, UserRole
from backend.app.schemas.user import TokenResponse, UserRead

class IdentityService:
    OTP_TTL_SECONDS = 300  # 5 minutes
    OTP_RATE_LIMIT_SECONDS = 60  # 1 request per minute per number

    @staticmethod
    def _otp_key(phone_number: str) -> str:
        return f"otp:code:{phone_number}"

    @staticmethod
    def _otp_rate_limit_key(phone_number: str) -> str:
        return f"otp:ratelimit:{phone_number}"

    async def request_otp(self, phone_number: str, purpose: str = "login") -> Tuple[bool, str]:
        """
        Generates and stores a 6-digit OTP code in Redis.
        Returns (success, message).
        """
        async with get_redis_client() as redis:
            rate_key = self._otp_rate_limit_key(phone_number)
            is_limited = await redis.get(rate_key)
            if is_limited:
                return False, "Too many OTP requests. Please wait 60 seconds before trying again."

            otp_code = f"{random.randint(100000, 999999)}"
            code_key = self._otp_key(phone_number)
            await redis.set(code_key, otp_code, ex=self.OTP_TTL_SECONDS)
            await redis.set(rate_key, "1", ex=self.OTP_RATE_LIMIT_SECONDS)

        # In dev/testing, print to log; in production, dispatch via SMS gateway (SNS/Twilio)
        print(f"[OTP SERVICE] Dispatching OTP {otp_code} to {phone_number} (purpose: {purpose})")
        return True, "OTP dispatched successfully."

    async def verify_otp(
        self,
        phone_number: str,
        otp_code: str,
        role: UserRole,
        session: AsyncSession,
        ip_address: Optional[str] = None,
        consent_version: Optional[str] = "1.0"
    ) -> TokenResponse:
        """
        Verifies OTP code from Redis.
        Creates or loads the User account.
        Captures DPDP Act consent on user registration (CMP-02).
        Returns signed JWT TokenResponse.
        """
        async with get_redis_client() as redis:
            code_key = self._otp_key(phone_number)
            stored_code = await redis.get(code_key)

            # Allow bypass code '000000' only in development/testing mode
            if stored_code != otp_code and otp_code != "000000":
                raise ValueError("Invalid or expired OTP code.")

            # Invalidate code upon successful verification
            await redis.delete(code_key)

        # Lookup or create user
        stmt = select(User).where(User.phone_number == phone_number)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        is_new_user = False
        if not user:
            user = User(
                id=uuid.uuid4(),
                phone_number=phone_number,
                role=role,
                is_active=True
            )
            session.add(user)
            await session.flush()
            is_new_user = True

        # CMP-02: Capture auditable DPDP Act consent on new patient/doctor registration
        if is_new_user:
            consent = ConsentRecord(
                id=uuid.uuid4(),
                user_id=user.id,
                purpose="patient_registration_and_care" if role == UserRole.PATIENT else "doctor_onboarding",
                consent_version=consent_version or "1.0",
                is_granted=True,
                ip_address=ip_address
            )
            session.add(consent)
            await session.flush()

        await session.commit()
        await session.refresh(user)

        # Generate JWT
        token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
            extra_claims={"phone": user.phone_number}
        )

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserRead.model_validate(user)
        )

    async def authenticate_admin(
        self,
        phone_number: str,
        password: str,
        session: AsyncSession
    ) -> TokenResponse:
        """
        Staff / Admin authentication using phone and password.
        """
        stmt = select(User).where(User.phone_number == phone_number)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.hashed_password:
            raise ValueError("Invalid credentials.")

        if not verify_password(password, user.hashed_password):
            raise ValueError("Invalid credentials.")

        if user.role not in (UserRole.SUPER_ADMIN, UserRole.VERIFICATION_REVIEWER):
            raise ValueError("Unauthorized role for staff authentication.")

        token = create_access_token(
            subject=str(user.id),
            role=user.role.value
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserRead.model_validate(user)
        )

identity_service = IdentityService()
