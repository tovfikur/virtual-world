"""
Land endpoints
Land management, search, transfer, and fencing operations
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional
import logging
import uuid

from app.db.session import get_db
from app.models.land import Land, Biome
from app.models.user import User
from app.schemas.land_schema import (
    LandResponse,
    LandUpdate,
    LandFence,
    LandTransfer,
    LandSearch
)
from app.dependencies import get_current_user, get_optional_user
from app.services.cache_service import cache_service
from app.config import CACHE_TTLS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lands", tags=["lands"])


@router.get("/{land_id}", response_model=LandResponse)
async def get_land(
    land_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get land details by ID.

    Returns comprehensive land information including:
    - Owner
    - Coordinates
    - Biome and elevation
    - Fencing status
    - Public message
    - Pricing
    """
    # Check cache
    cache_key = f"land:{land_id}"
    cached_land = await cache_service.get(cache_key)

    if cached_land:
        logger.debug(f"Cache hit for land {land_id}")
        return LandResponse(**cached_land)

    try:
        land_uuid = uuid.UUID(land_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid land ID format"
        )

    result = await db.execute(
        select(Land).where(Land.land_id == land_uuid)
    )
    land = result.scalar_one_or_none()

    if not land:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found"
        )

    # Cache the result
    land_dict = land.to_dict()
    await cache_service.set(cache_key, land_dict, ttl=CACHE_TTLS["land"])

    return LandResponse(**land_dict)


@router.get("/", response_model=dict)
async def search_lands(
    biome: Optional[str] = Query(None),
    min_price_bdt: Optional[int] = Query(None, ge=0),
    max_price_bdt: Optional[int] = Query(None, ge=0),
    for_sale: Optional[bool] = Query(None),
    owner_id: Optional[str] = Query(None),
    x: Optional[int] = Query(None),
    y: Optional[int] = Query(None),
    radius: Optional[int] = Query(None, ge=1, le=100),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at_desc"),
    db: AsyncSession = Depends(get_db)
):
    """
    Search and filter lands.

    Supports:
    - Filtering by biome, price range, sale status, owner
    - Proximity search (x, y, radius)
    - Pagination
    - Sorting (price_asc, price_desc, created_at_asc, created_at_desc)
    """
    # Build query
    query = select(Land).where(Land.deleted_at.is_(None))

    # Apply filters
    if biome:
        try:
            biome_enum = Biome(biome)
            query = query.where(Land.biome == biome_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid biome. Must be one of: {[b.value for b in Biome]}"
            )

    if min_price_bdt is not None:
        query = query.where(Land.price_base_bdt >= min_price_bdt)

    if max_price_bdt is not None:
        query = query.where(Land.price_base_bdt <= max_price_bdt)

    if for_sale is not None:
        query = query.where(Land.for_sale == for_sale)

    if owner_id:
        try:
            owner_uuid = uuid.UUID(owner_id)
            query = query.where(Land.owner_id == owner_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid owner ID format"
            )

    # Proximity search
    if x is not None and y is not None and radius is not None:
        query = query.where(
            and_(
                Land.x.between(x - radius, x + radius),
                Land.y.between(y - radius, y + radius)
            )
        )

    # Apply sorting
    if sort == "price_asc":
        query = query.order_by(Land.price_base_bdt.asc())
    elif sort == "price_desc":
        query = query.order_by(Land.price_base_bdt.desc())
    elif sort == "created_at_asc":
        query = query.order_by(Land.created_at.asc())
    else:  # created_at_desc
        query = query.order_by(Land.created_at.desc())

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    lands = result.scalars().all()

    return {
        "data": [land.to_dict() for land in lands],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if total > 0 else 0,
            "has_next": page * limit < total,
            "has_prev": page > 1
        }
    }


@router.put("/{land_id}", response_model=LandResponse)
async def update_land(
    land_id: str,
    land_data: LandUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update land details (public message, etc.).

    Only land owner can update their land.
    """
    try:
        land_uuid = uuid.UUID(land_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid land ID format"
        )

    result = await db.execute(
        select(Land).where(Land.land_id == land_uuid)
    )
    land = result.scalar_one_or_none()

    if not land:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found"
        )

    # Check ownership
    if str(land.owner_id) != current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own land"
        )

    # Update fields
    update_data = land_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(land, field, value)

    await db.commit()
    await db.refresh(land)

    # Invalidate cache
    await cache_service.delete(f"land:{land_id}")

    logger.info(f"Land updated: {land_id}")

    return LandResponse(**land.to_dict())


@router.post("/{land_id}/fence")
async def manage_fence(
    land_id: str,
    fence_data: LandFence,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Enable or disable land fencing.

    - **fenced**: True to enable fence, False to disable
    - **passcode**: 4-digit passcode (required when enabling fence)

    Returns updated fencing status.
    """
    try:
        land_uuid = uuid.UUID(land_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid land ID format"
        )

    result = await db.execute(
        select(Land).where(Land.land_id == land_uuid)
    )
    land = result.scalar_one_or_none()

    if not land:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found"
        )

    # Check ownership
    if str(land.owner_id) != current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage fencing on your own land"
        )

    # Enable or disable fence
    if fence_data.fenced:
        if not fence_data.passcode:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passcode is required when enabling fence"
            )
        land.enable_fence(fence_data.passcode)
        logger.info(f"Fence enabled on land {land_id}")
    else:
        land.disable_fence()
        logger.info(f"Fence disabled on land {land_id}")

    await db.commit()
    await db.refresh(land)

    # Invalidate cache
    await cache_service.delete(f"land:{land_id}")

    return {
        "land_id": str(land.land_id),
        "fenced": land.fenced,
        "passcode_updated_at": land.passcode_updated_at.isoformat() if land.passcode_updated_at else None
    }


@router.post("/{land_id}/transfer")
async def transfer_land(
    land_id: str,
    transfer_data: LandTransfer,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Transfer land to another user (gift, no payment).

    For marketplace transfers with payment, use the marketplace endpoints.
    """
    try:
        land_uuid = uuid.UUID(land_id)
        new_owner_uuid = uuid.UUID(transfer_data.new_owner_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    # Get land
    result = await db.execute(
        select(Land).where(Land.land_id == land_uuid)
    )
    land = result.scalar_one_or_none()

    if not land:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found"
        )

    # Check ownership
    if str(land.owner_id) != current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only transfer your own land"
        )

    # Verify new owner exists
    result = await db.execute(
        select(User).where(User.user_id == new_owner_uuid)
    )
    new_owner = result.scalar_one_or_none()

    if not new_owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="New owner not found"
        )

    # Cannot transfer to self
    if str(land.owner_id) == str(new_owner_uuid):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transfer land to yourself"
        )

    # Store old owner
    previous_owner_id = land.owner_id

    # Transfer ownership
    land.owner_id = new_owner_uuid
    land.fenced = False  # Remove fence on transfer
    land.passcode_hash = None
    land.for_sale = False  # Remove from sale

    await db.commit()
    await db.refresh(land)

    # Invalidate caches
    await cache_service.delete(f"land:{land_id}")
    await cache_service.delete(f"user_lands:{previous_owner_id}")
    await cache_service.delete(f"user_lands:{new_owner_uuid}")

    logger.info(f"Land transferred: {land_id} from {previous_owner_id} to {new_owner_uuid}")

    return {
        "land_id": str(land.land_id),
        "previous_owner_id": str(previous_owner_id),
        "new_owner_id": str(land.owner_id),
        "transfer_completed_at": land.updated_at.isoformat(),
        "message": transfer_data.message
    }


@router.get("/{land_id}/heatmap")
async def get_land_heatmap(
    land_id: str,
    radius: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get pricing heatmap for region around land.

    Returns nearby lands with their prices for visualization.
    """
    try:
        land_uuid = uuid.UUID(land_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid land ID format"
        )

    result = await db.execute(
        select(Land).where(Land.land_id == land_uuid)
    )
    land = result.scalar_one_or_none()

    if not land:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found"
        )

    # Find nearby lands
    result = await db.execute(
        select(Land).where(
            and_(
                Land.x.between(land.x - radius, land.x + radius),
                Land.y.between(land.y - radius, land.y + radius),
                Land.deleted_at.is_(None)
            )
        )
    )
    nearby_lands = result.scalars().all()

    prices = [l.price_base_bdt for l in nearby_lands]

    return {
        "center_land_id": str(land.land_id),
        "center_coordinates": {"x": land.x, "y": land.y},
        "radius": radius,
        "price_range": {
            "min_bdt": min(prices) if prices else 0,
            "max_bdt": max(prices) if prices else 0,
            "avg_bdt": sum(prices) // len(prices) if prices else 0
        },
        "nearby_lands": [
            {
                "land_id": str(l.land_id),
                "coordinates": {"x": l.x, "y": l.y},
                "distance_units": max(abs(l.x - land.x), abs(l.y - land.y)),
                "price_bdt": l.price_base_bdt,
                "biome": l.biome.value,
                "for_sale": l.for_sale
            }
            for l in nearby_lands[:50]  # Limit to 50 for performance
        ],
        "total_nearby": len(nearby_lands)
    }
