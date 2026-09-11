import json
from datetime import datetime, timedelta, timezone

from jose import jwt

from backend.app.core.config import settings


def generate_livekit_token(
    room_name: str, participant_identity: str, participant_name: str, role: str,
    is_admin: bool = False, ttl_minutes: int = 60,
) -> str:
    """Create a short-lived LiveKit-compatible access token for one participant."""
    now = datetime.now(timezone.utc)
    claims = {
        "iss": settings.LIVEKIT_API_KEY,
        "sub": participant_identity,
        "name": participant_name,
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
        "video": {
            "room": room_name, "roomJoin": True, "canPublish": True,
            "canSubscribe": True, "canPublishData": True, "roomRecord": is_admin,
        },
        "metadata": json.dumps({"role": role, "user_id": participant_identity}),
    }
    return jwt.encode(claims, settings.LIVEKIT_API_SECRET, algorithm="HS256")


def get_livekit_url() -> str:
    return settings.LIVEKIT_URL
