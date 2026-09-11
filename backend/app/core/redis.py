import json
import uuid
from typing import Any

import redis.asyncio as aioredis
from backend.app.core.config import settings


def get_redis_client() -> aioredis.Redis:
    return aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True
    )

class DistributedLockManager:
    @staticmethod
    def format_slot_key(doctor_id: str, slot_iso: str) -> str:
        return f"lock:doctor:{doctor_id}:slot:{slot_iso}"

    async def acquire_lock(self, key: str, ttl_seconds: int = 600) -> str | None:
        """
        Attempts to acquire a distributed lock using Redis SETNX with TTL.
        Returns unique token string if acquired, None if lock is already held.
        """
        client = get_redis_client()
        try:
            token = str(uuid.uuid4())
            acquired = await client.set(key, token, ex=ttl_seconds, nx=True)
            if acquired:
                return token
            return None
        finally:
            await client.aclose()

    async def release_lock(self, key: str, token: str) -> bool:
        """
        Releases the distributed lock using a Lua script to ensure atomicity
        (only releases if the value matches the acquired token).
        """
        client = get_redis_client()
        lua_release = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        try:
            res = await client.eval(lua_release, 1, key, token)
            return bool(res == 1)
        finally:
            await client.aclose()

    async def acquire_slot_lock(self, doctor_id: str, slot_iso: str, ttl_seconds: int = 600) -> str | None:
        key = self.format_slot_key(doctor_id, slot_iso)
        return await self.acquire_lock(key, ttl_seconds=ttl_seconds)

    async def release_slot_lock(self, doctor_id: str, slot_iso: str, token: str) -> bool:
        key = self.format_slot_key(doctor_id, slot_iso)
        return await self.release_lock(key, token)

async def publish_event(channel: str, event_type: str, data: dict[str, Any]) -> int:
    """
    Publishes an event to a Redis Pub/Sub channel for the Node.js real-time gateway.
    """
    client = get_redis_client()
    payload = {
        "event_type": event_type,
        "data": data
    }
    try:
        return await client.publish(channel, json.dumps(payload))
    finally:
        await client.aclose()

lock_manager = DistributedLockManager()
