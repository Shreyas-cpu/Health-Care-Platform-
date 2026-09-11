import base64
import json
import logging
import os
import uuid
from typing import Any

import firebase_admin
from firebase_admin import auth as firebase_auth_admin, credentials
from fastapi import HTTPException, status
import jwt
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.consent import ConsentRecord
from backend.app.models.patient import Patient
from backend.app.models.user import User, UserRole

logger = logging.getLogger(__name__)


def _get_or_init_firebase_app():
    """Initializes the default Firebase Admin SDK app if not already initialized."""
    if not firebase_admin._apps:
        try:
            if settings.FIREBASE_CREDENTIALS_PATH and os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred, {"projectId": settings.FIREBASE_PROJECT_ID})
                logger.info("Firebase Admin initialized with service account credentials.")
            else:
                options = {"projectId": settings.FIREBASE_PROJECT_ID} if settings.FIREBASE_PROJECT_ID else None
                firebase_admin.initialize_app(options=options)
                logger.info("Firebase Admin initialized with default application options.")
        except Exception as exc:
            logger.warning(
                "Could not initialize live Firebase Admin app (%s). "
                "Sandbox/mock verification fallback will be enabled.",
                exc
            )


def create_mock_firebase_token(
    uid: str,
    phone_number: str | None = None,
    email: str | None = None,
    name: str | None = None,
    role: str | None = None,
) -> str:
    """Helper to generate a mock Firebase token for testing and local sandbox."""
    payload = {
        "uid": uid,
        "sub": uid,
        "phone_number": phone_number,
        "email": email,
        "email_verified": True if email else False,
        "name": name,
        "role": role,
        "iss": f"https://securetoken.google.com/{settings.FIREBASE_PROJECT_ID}",
        "aud": settings.FIREBASE_PROJECT_ID,
        "auth_time": 1700000000,
        "user_id": uid,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"mock-firebase-{encoded}"


def verify_firebase_id_token(id_token: str) -> dict[str, Any]:
    """
    Verifies a Firebase ID token.
    1. If token starts with 'mock-firebase-', decodes embedded JSON payload.
    2. Tries live verification using firebase_admin.auth.verify_id_token.
    3. If live verification fails and FIREBASE_MOCK_AUTH is enabled, attempts
       unverified JWT payload decode (useful for unit tests without Google credentials).
    """
    if not id_token or not isinstance(id_token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Firebase ID token format.",
        )

    # 1. Check for mock token format
    if id_token.startswith("mock-firebase-"):
        payload_b64 = id_token.replace("mock-firebase-", "")
        try:
            # Pad base64 if necessary
            missing_padding = len(payload_b64) % 4
            if missing_padding:
                payload_b64 += "=" * (4 - missing_padding)
            payload_data = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
            if "uid" not in payload_data and "sub" in payload_data:
                payload_data["uid"] = payload_data["sub"]
            return payload_data
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Malformed mock Firebase token: {e}",
            )

    # 2. Try live verification with firebase-admin
    _get_or_init_firebase_app()
    try:
        if firebase_admin._apps:
            verified_claims = firebase_auth_admin.verify_id_token(id_token)
            if "uid" not in verified_claims and "sub" in verified_claims:
                verified_claims["uid"] = verified_claims["sub"]
            return verified_claims
    except Exception as live_err:
        logger.debug("Live Firebase token verification failed: %s", live_err)
        # 3. Fallback to mock decode if permitted
        if settings.FIREBASE_MOCK_AUTH and id_token.count(".") == 2:
            try:
                unverified = jwt.decode(id_token, options={"verify_signature": False})
                uid = unverified.get("user_id") or unverified.get("sub") or unverified.get("uid")
                if uid:
                    unverified["uid"] = uid
                    return unverified
            except Exception:
                pass

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired Firebase ID token: {live_err}",
        )

    # Fallback if no firebase app and mock auth allowed
    if settings.FIREBASE_MOCK_AUTH and id_token.count(".") == 2:
        try:
            unverified = jwt.decode(id_token, options={"verify_signature": False})
            uid = unverified.get("user_id") or unverified.get("sub") or unverified.get("uid")
            if uid:
                unverified["uid"] = uid
                return unverified
        except Exception as decode_err:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Firebase ID token format: {decode_err}",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Firebase authentication failed.",
    )


async def sync_firebase_user(
    token_payload: dict[str, Any],
    role: UserRole,
    session: AsyncSession,
    consent_version: str = "v1.0",
    client_ip: str | None = None,
    full_name: str | None = None,
) -> tuple[User, bool]:
    """
    Synchronizes Firebase user identity with the local database:
    - Finds user by firebase_uid, phone_number, or email.
    - If user does not exist, provisions a new User record and associated role profile.
    - Complies with DPDP Act by registering ConsentRecord on initial provisioning.
    - Returns (user, is_new_user).
    """
    uid: str = token_payload.get("uid") or token_payload.get("sub")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firebase token payload missing UID/subject claim.",
        )

    phone_number: str | None = token_payload.get("phone_number")
    email: str | None = token_payload.get("email")
    display_name: str | None = full_name or token_payload.get("name")

    # 1. Search existing user by firebase_uid
    stmt = select(User).where(User.firebase_uid == uid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    is_new_user = False

    # 2. If not found by firebase_uid, check by phone or email
    if not user:
        conditions = []
        if phone_number:
            conditions.append(User.phone_number == phone_number)
        if email:
            conditions.append(User.email == email)

        if conditions:
            stmt_match = select(User).where(or_(*conditions))
            res_match = await session.execute(stmt_match)
            user = res_match.scalar_one_or_none()

        if user:
            # Link existing user to firebase_uid
            user.firebase_uid = uid
            if not user.email and email:
                user.email = email
            if not user.phone_number and phone_number:
                user.phone_number = phone_number
        else:
            # Provision brand new user
            is_new_user = True
            user = User(
                id=uuid.uuid4(),
                firebase_uid=uid,
                phone_number=phone_number,
                email=email,
                role=role,
                is_active=True,
            )
            session.add(user)
            await session.flush()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been suspended or deactivated.",
        )

    # 3. DPDP Act Consent Capture (on first registration or if consent record not yet logged)
    consent_stmt = select(ConsentRecord).where(
        ConsentRecord.user_id == user.id,
        ConsentRecord.purpose == f"{user.role.value}_registration_and_care",
    )
    existing_consent = (await session.execute(consent_stmt)).scalar_one_or_none()

    if not existing_consent:
        consent = ConsentRecord(
            id=uuid.uuid4(),
            user_id=user.id,
            purpose=f"{user.role.value}_registration_and_care",
            consent_version=consent_version,
            is_granted=True,
            ip_address=client_ip,
        )
        session.add(consent)

    # 4. Role Profile Provisioning for Patient
    if user.role == UserRole.PATIENT:
        pat_stmt = select(Patient).where(Patient.user_id == user.id)
        patient = (await session.execute(pat_stmt)).scalar_one_or_none()
        if not patient:
            patient = Patient(
                user_id=user.id,
                full_name=display_name or "Patient",
            )
            session.add(patient)
        elif display_name and not patient.full_name:
            patient.full_name = display_name

    await session.commit()
    await session.refresh(user)
    return user, is_new_user
