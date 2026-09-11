import random
import uuid

import pytest_asyncio
from backend.app.core.config import settings
from backend.app.models.user import User, UserRole
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


def random_digits(n: int) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(n))

@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    # Use NullPool so each test connection is isolated to the active event loop
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, echo=False)
    async_session = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    async with async_session() as session:
        yield session
        await session.rollback()
    await engine.dispose()

@pytest_asyncio.fixture
async def sample_patient(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        phone_number=f"+9198{random_digits(8)}",
        role=UserRole.PATIENT,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture
async def sample_doctor(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        phone_number=f"+9197{random_digits(8)}",
        role=UserRole.DOCTOR,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
