import pytest
from backend.app.core.config import settings
from backend.app.core.redis import lock_manager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_settings_loaded():
    assert settings.PROJECT_NAME == "Digital Healthcare Services Platform"
    assert settings.API_V1_STR == "/api/v1"
    assert settings.DATABASE_URL is not None
    assert settings.REDIS_URL is not None

@pytest.mark.asyncio
async def test_database_connectivity(db_session: AsyncSession):
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1

@pytest.mark.asyncio
async def test_btree_gist_extension_present(db_session: AsyncSession):
    result = await db_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname = 'btree_gist'")
    )
    assert result.scalar() == "btree_gist"

@pytest.mark.asyncio
async def test_redis_distributed_lock():
    key = "test:lock:sample"
    token1 = await lock_manager.acquire_lock(key, ttl_seconds=10)
    assert token1 is not None

    # Second attempt while held should fail
    token2 = await lock_manager.acquire_lock(key, ttl_seconds=10)
    assert token2 is None

    # Release with token1 should succeed
    released = await lock_manager.release_lock(key, token1)
    assert released is True

    # Now can be acquired again
    token3 = await lock_manager.acquire_lock(key, ttl_seconds=10)
    assert token3 is not None
    await lock_manager.release_lock(key, token3)
