from decimal import Decimal

from backend.app.core.database import get_db
from backend.app.schemas.search import DoctorSearchFilters, DoctorSearchResponse
from backend.app.services.search_index import search_doctors
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/search", tags=["Search Catalog"])


@router.get("/doctors", response_model=DoctorSearchResponse)
async def search_catalog(
    specialty: str | None = None,
    locality: str | None = None,
    city: str | None = None,
    min_fee: Decimal | None = None,
    max_fee: Decimal | None = None,
    gender: str | None = None,
    video_available: bool | None = None,
    available_today: bool | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    return await search_doctors(
        session,
        DoctorSearchFilters(
            specialty=specialty,
            locality=locality,
            city=city,
            min_fee=min_fee,
            max_fee=max_fee,
            gender=gender,
            video_available=video_available,
            available_today=available_today,
            page=page,
            limit=limit,
        ),
    )
