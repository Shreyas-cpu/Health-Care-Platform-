"""PostgreSQL-backed doctor catalog with a short Redis query cache."""
import hashlib
import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.redis import get_redis_client
from backend.app.models.clinic import Clinic
from backend.app.models.doctor import Doctor, VerificationStatus
from backend.app.schemas.search import ClinicRead, DoctorSearchFilters, DoctorSearchResponse, DoctorSearchResult

CACHE_PREFIX = "cache:search:query:"
CACHE_TTL_SECONDS = 300


def _cache_key(filters: DoctorSearchFilters) -> str:
    params = filters.model_dump(mode="json", exclude_none=True)
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return CACHE_PREFIX + hashlib.md5(payload.encode()).hexdigest()


def _result(doctor: Doctor) -> DoctorSearchResult:
    clinic = ClinicRead.model_validate(doctor.clinic) if doctor.clinic else None
    return DoctorSearchResult(
        doctor_id=doctor.user_id, full_name=doctor.full_name, specialty=doctor.specialty,
        years_experience=doctor.years_experience, bio=doctor.bio, gender=doctor.gender,
        in_person_fee=doctor.in_person_fee, video_fee=doctor.video_fee,
        listing_online=doctor.listing_online, video_enabled=doctor.video_enabled, clinic=clinic,
    )


async def invalidate_search_cache() -> int:
    """Delete all derived catalog query results, returning keys removed."""
    client = get_redis_client()
    try:
        keys = [key async for key in client.scan_iter(match="cache:search:*")]
        return int(await client.delete(*keys)) if keys else 0
    except Exception:
        return 0
    finally:
        await client.aclose()


async def search_doctors(session: AsyncSession, filters: DoctorSearchFilters) -> DoctorSearchResponse:
    """Search only verified, published doctors. RUL-02 is enforced in every query."""
    key = _cache_key(filters)
    client = get_redis_client()
    try:
        cached = await client.get(key)
        if cached:
            return DoctorSearchResponse.model_validate_json(cached)
    except Exception:
        cached = None
    finally:
        await client.aclose()

    # An outer join keeps doctors with no clinic in the unfiltered catalog.
    statement = select(Doctor).outerjoin(Clinic).options(selectinload(Doctor.clinic)).where(
        Doctor.verification_status == VerificationStatus.VERIFIED,
        Doctor.listing_online.is_(True),
    )
    count_statement = select(func.count(Doctor.user_id)).outerjoin(Clinic).where(
        Doctor.verification_status == VerificationStatus.VERIFIED,
        Doctor.listing_online.is_(True),
    )

    predicates: list[Any] = []
    if filters.specialty:
        predicates.append(Doctor.specialty.ilike(f"%{filters.specialty}%"))
    if filters.locality:
        predicates.append(Clinic.locality.ilike(f"%{filters.locality}%"))
    if filters.city:
        predicates.append(Clinic.city.ilike(f"%{filters.city}%"))
    if filters.min_fee is not None:
        predicates.append(Doctor.in_person_fee >= filters.min_fee)
    if filters.max_fee is not None:
        predicates.append(Doctor.in_person_fee <= filters.max_fee)
    if filters.gender:
        predicates.append(Doctor.gender.ilike(filters.gender))
    if filters.video_available is True:
        predicates.append(Doctor.video_enabled.is_(True))

    if predicates:
        statement = statement.where(*predicates)
        count_statement = count_statement.where(*predicates)

    total = int((await session.execute(count_statement)).scalar_one())
    statement = statement.order_by(Doctor.full_name).offset((filters.page - 1) * filters.limit).limit(filters.limit)
    doctors = (await session.execute(statement)).scalars().all()
    response = DoctorSearchResponse(items=[_result(doctor) for doctor in doctors], total=total)

    client = get_redis_client()
    try:
        await client.set(key, response.model_dump_json(), ex=CACHE_TTL_SECONDS)
    except Exception:
        pass
    finally:
        await client.aclose()
    return response
