import uuid

from backend.app.api.deps import get_current_user, require_roles
from backend.app.core.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.schemas.teleconsultation import (
    ChatMessageCreate,
    ChatMessageRead,
    LiveKitTokenResponse,
    RecordingConsentRequest,
    TeleconsultationSessionRead,
)
from backend.app.services.chat_service import get_chat_history, save_chat_message
from backend.app.services.livekit_client import generate_livekit_token, get_livekit_url
from backend.app.services.teleconsultation_service import (
    doctor_start_session,
    end_session,
    get_or_create_session,
    patient_enter_waiting_room,
    update_recording_consent,
)
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/teleconsultation", tags=["Teleconsultation"])


@router.post("/{appointment_id}/token", response_model=LiveKitTokenResponse)
async def create_token(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    tele_session = await get_or_create_session(session, appointment_id)
    await session.commit()
    await session.refresh(tele_session)
    return LiveKitTokenResponse(
        token=generate_livekit_token(
            tele_session.room_name,
            str(current_user.id),
            current_user.phone_number,
            current_user.role.value,
        ),
        room_name=tele_session.room_name,
        livekit_url=get_livekit_url(),
    )


@router.post(
    "/{appointment_id}/waiting-room", response_model=TeleconsultationSessionRead
)
async def enter_waiting_room(
    appointment_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.PATIENT)),
    session: AsyncSession = Depends(get_db),
):
    return await patient_enter_waiting_room(session, appointment_id, current_user.id)


@router.post("/{appointment_id}/start", response_model=TeleconsultationSessionRead)
async def start_session(
    appointment_id: uuid.UUID,
    current_user: User = Depends(require_roles(UserRole.DOCTOR)),
    session: AsyncSession = Depends(get_db),
):
    return await doctor_start_session(session, appointment_id, current_user.id)


@router.post("/{appointment_id}/end", response_model=TeleconsultationSessionRead)
async def complete_session(
    appointment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await end_session(session, appointment_id, current_user.id)


@router.post(
    "/{appointment_id}/consent-recording", response_model=TeleconsultationSessionRead
)
async def consent_recording(
    appointment_id: uuid.UUID,
    data: RecordingConsentRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await update_recording_consent(
        session, appointment_id, current_user.id, data.consent
    )


@router.get("/{appointment_id}/chat", response_model=list[ChatMessageRead])
async def chat_history(
    appointment_id: uuid.UUID, session: AsyncSession = Depends(get_db)
):
    return await get_chat_history(session, appointment_id)


@router.post("/{appointment_id}/chat", response_model=ChatMessageRead)
async def post_chat_message(
    appointment_id: uuid.UUID,
    data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await save_chat_message(
        session,
        appointment_id,
        current_user.id,
        current_user.role.value,
        data.message_text,
        data.file_s3_key,
    )
