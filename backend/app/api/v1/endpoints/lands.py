"""
Land endpoints
Land management, search, transfer, and fencing operations
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional, Dict, List
import logging
import uuid

from app.db.session import get_db
from app.models.land import Land, Biome
from app.models.land_chat_access import LandChatAccess
from app.models.user import User
from app.schemas.land_schema import (
    LandResponse,
    LandUpdate,
    LandFence,
    LandTransfer,
    LandSearch,
    LandChatAccessList,
    LandChatAccessEntry,
    LandChatAccessRequest,
    LandChatAccessRemove,
    LandChatAccessSearchResult,
)
from app.dependencies import get_current_user, get_optional_user
from app.services.cache_service import cache_service
from app.config import CACHE_TTLS
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lands", tags=["lands"])


class LandClaimRequest(BaseModel):
    """Schema for claiming/purchasing land"""
    x: int
    y: int
    biome: str
    elevation: float
    price_base_bdt: int


async def _serialize_land(
    land: Land,
    db: AsyncSession,
    owner_cache: Optional[Dict[str, Optional[str]]] = None
) -> dict:
    """Convert Land ORM object to serializable dict with owner metadata."""
    owner_username = None

    if land.owner_id:
        cache_key = str(land.owner_id)
        if owner_cache is not None and cache_key in owner_cache:
            owner_username = owner_cache[cache_key]
        else:
            owner_result = await db.execute(
                select(User.username).where(User.user_id == land.owner_id)
            )
            owner_username = owner_result.scalar_one_or_none()
            if owner_cache is not None:
                owner_cache[cache_key] = owner_username

    land_dict = land.to_dict()
    land_dict["owner_username"] = owner_username
    return land_dict


async def _get_land_or_404(land_id: str, db: AsyncSession) -> Land:
    """Fetch land by ID or raise HTTP 404."""
    try:
        land_uuid = uuid.UUID(land_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid land ID format",
        )

    result = await db.execute(select(Land).where(Land.land_id == land_uuid))
    land = result.scalar_one_or_none()

    if not land:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found",
        )

    return land


async def _require_land_owner(
    land: Land,
    current_user: dict,
) -> None:
    """Ensure current user owns the provided land."""
    if str(land.owner_id) != current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the land owner can manage this resource",
        )


@router.get("/coordinates/{x}/{y}", response_model=LandResponse)
async def get_land_by_coordinates(
    x: int,
    y: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get land details by world coordinates.

    Returns land information when the parcel is claimed (persisted in DB).
    """
    width_expr = func.coalesce(Land.width, 1)
    height_expr = func.coalesce(Land.height, 1)

    result = await db.execute(
        select(Land)
        .where(
            Land.x <= x,
            (Land.x + width_expr) > x,
            Land.y <= y,
            (Land.y + height_expr) > y
        )
        .order_by(Land.created_at.desc())
        .limit(1)
    )
    land = result.scalars().first()

    if not land:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Land not found"
        )

    land_dict = await _serialize_land(land, db)
    return LandResponse(**land_dict)


@router.get("/owner/{owner_id}/coordinates")
async def get_owner_land_coordinates(
    owner_id: str,
    limit: int = Query(5000, ge=1, le=20000),
    db: AsyncSession = Depends(get_db)
):
    """
    Get coordinates of lands owned by a user.

    Returns a lightweight list of coordinates for highlighting ownership.
    """
    try:
        owner_uuid = uuid.UUID(owner_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid owner ID format"
        )

    # Verify owner exists
    owner_result = await db.execute(
        select(User.username).where(User.user_id == owner_uuid)
    )
    owner_username = owner_result.scalar_one_or_none()

    if owner_username is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Owner not found"
        )

    result = await db.execute(
        select(
            Land.land_id,
            Land.x,
            Land.y,
            Land.width,
            Land.height,
            Land.biome,
            Land.price_base_bdt
        )
        .where(
            Land.owner_id == owner_uuid
        )
    )

    rows = result.all()
    total_tiles = sum(
        (row.width or 1) * (row.height or 1)
        for row in rows
    )

    lands = []

    for row in rows:
        width = row.width or 1
        height = row.height or 1
        biome_value = row.biome.value if row.biome else None

        for dx in range(width):
            for dy in range(height):
                tile_x = row.x + dx
                tile_y = row.y + dy
                lands.append({
                    "land_id": str(row.land_id),
                    "x": tile_x,
                    "y": tile_y,
                    "biome": biome_value,
                    "price_base_bdt": row.price_base_bdt
                })

                if len(lands) >= limit:
                    break
            if len(lands) >= limit:
                break

        if len(lands) >= limit:
            break

    return {
        "owner_id": owner_id,
        "owner_username": owner_username,
        "count": total_tiles,
        "lands": lands,
        "limit": limit
    }


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
        cached_land.setdefault("owner_username", None)
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

    land_dict = await _serialize_land(land, db)

    # Cache the result
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
    query = select(Land)

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

    owner_cache: dict[str, Optional[str]] = {}
    serialized_lands = []
    for land in lands:
        serialized_lands.append(await _serialize_land(land, db, owner_cache))

    return {
        "data": serialized_lands,
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

    land_dict = await _serialize_land(land, db)
    return LandResponse(**land_dict)


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


@router.get("/{land_id}/chat/access", response_model=LandChatAccessList)
async def get_land_chat_access(
    land_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List explicit chat access entries for a land."""
    land = await _get_land_or_404(land_id, db)
    await _require_land_owner(land, current_user)

    result = await db.execute(
        select(LandChatAccess, User.username)
        .join(User, LandChatAccess.user_id == User.user_id)
        .where(LandChatAccess.land_id == land.land_id)
        .order_by(User.username.asc())
    )

    entries: List[LandChatAccessEntry] = []
    for access, username in result.all():
        entries.append(
            LandChatAccessEntry(
                access_id=str(access.access_id),
                land_id=str(access.land_id),
                user_id=str(access.user_id),
                username=username,
                can_read=access.can_read,
                can_write=access.can_write,
                created_at=access.created_at,
            )
        )

    return LandChatAccessList(
        land_id=land_id,
        restricted=len(entries) > 0,
        entries=entries,
    )


@router.post("/{land_id}/chat/access", response_model=LandChatAccessEntry)
async def add_land_chat_access(
    land_id: str,
    access_request: LandChatAccessRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Grant or update chat access for a user by username."""
    land = await _get_land_or_404(land_id, db)
    await _require_land_owner(land, current_user)

    username_search = access_request.username.lower()
    user_result = await db.execute(
        select(User).where(func.lower(User.username) == username_search)
    )
    target_user = user_result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if target_user.user_id == land.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owners already have full access to their own land",
        )

    target_land_ids = [land.land_id]
    if access_request.apply_to_all_fenced:
        all_land_result = await db.execute(
            select(Land.land_id)
            .where(Land.owner_id == land.owner_id, Land.fenced.is_(True))
        )
        target_land_ids = [row[0] for row in all_land_result.scalars().all()] or [land.land_id]

    upserted_entry = None
    for target_land_id in target_land_ids:
        result = await db.execute(
            select(LandChatAccess).where(
                LandChatAccess.land_id == target_land_id,
                LandChatAccess.user_id == target_user.user_id,
            )
        )
        access_entry = result.scalar_one_or_none()

        if access_entry:
            access_entry.can_read = access_request.can_read
            access_entry.can_write = access_request.can_write
        else:
            access_entry = LandChatAccess(
                land_id=target_land_id,
                user_id=target_user.user_id,
                can_read=access_request.can_read,
                can_write=access_request.can_write,
            )
            db.add(access_entry)

        if target_land_id == land.land_id:
            upserted_entry = access_entry

    await db.commit()

    if upserted_entry is None:
        result = await db.execute(
            select(LandChatAccess).where(
                LandChatAccess.land_id == land.land_id,
                LandChatAccess.user_id == target_user.user_id,
            )
        )
        upserted_entry = result.scalar_one()

    return LandChatAccessEntry(
        access_id=str(upserted_entry.access_id),
        land_id=str(upserted_entry.land_id),
        user_id=str(upserted_entry.user_id),
        username=target_user.username,
        can_read=upserted_entry.can_read,
        can_write=upserted_entry.can_write,
        created_at=upserted_entry.created_at,
    )


@router.delete("/{land_id}/chat/access")
async def remove_land_chat_access(
    land_id: str,
    remove_request: LandChatAccessRemove,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove chat access for a specific username."""
    land = await _get_land_or_404(land_id, db)
    await _require_land_owner(land, current_user)

    username_search = remove_request.username.lower()
    user_result = await db.execute(
        select(User).where(func.lower(User.username) == username_search)
    )
    target_user = user_result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if target_user.user_id == land.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner access cannot be revoked",
        )

    access_result = await db.execute(
        select(LandChatAccess).where(
            LandChatAccess.land_id == land.land_id,
            LandChatAccess.user_id == target_user.user_id,
        )
    )
    access_entry = access_result.scalar_one_or_none()

    if not access_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not have chat access to this land",
        )

    await db.delete(access_entry)
    await db.commit()

    return {
        "status": "success",
        "message": f"Removed chat access for {target_user.username}",
    }


@router.get(
    "/{land_id}/chat/access/search",
    response_model=List[LandChatAccessSearchResult],
)
async def search_users_for_chat_access(
    land_id: str,
    username: str = Query(..., min_length=2, max_length=64),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search users by username substring to grant chat access."""
    land = await _get_land_or_404(land_id, db)
    await _require_land_owner(land, current_user)

    normalized = username.strip().lower()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username query is required",
        )

    access_ids_result = await db.execute(
        select(LandChatAccess.user_id).where(LandChatAccess.land_id == land.land_id)
    )
    existing_user_ids = {
        str(row[0]) for row in access_ids_result.all() if row[0] is not None
    }

    search_pattern = f"%{normalized}%"
    result = await db.execute(
        select(User)
        .where(func.lower(User.username).like(search_pattern))
        .order_by(User.username.asc())
        .limit(10)
    )

    matches: List[LandChatAccessSearchResult] = []
    for user_obj in result.scalars():
        if user_obj.user_id == land.owner_id:
            continue
        matches.append(
            LandChatAccessSearchResult(
                user_id=str(user_obj.user_id),
                username=user_obj.username,
                has_access=str(user_obj.user_id) in existing_user_ids,
            )
        )

    return matches


@router.post("/claim", response_model=LandResponse)
async def claim_land(
    claim_data: LandClaimRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Purchase/claim unclaimed land at specific coordinates.

    This endpoint allows users to purchase land that hasn't been claimed yet.
    The land is generated from world data and assigned to the user.

    Args:
        claim_data: Land coordinates and details
        current_user: Current authenticated user
        db: Database session

    Returns:
        Newly claimed land details

    Raises:
        400: If land is already claimed or insufficient balance
        404: If coordinates are invalid
    """
    user_id = uuid.UUID(current_user["sub"])

    # Check if land already exists at these coordinates
    result = await db.execute(
        select(Land).where(
            and_(
                Land.x == claim_data.x,
                Land.y == claim_data.y
            )
        )
    )
    existing_land = result.scalar_one_or_none()

    if existing_land:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Land at ({claim_data.x}, {claim_data.y}) is already claimed"
        )

    # Get user to check balance
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user has sufficient balance
    if user.balance_bdt < claim_data.price_base_bdt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance. Need {claim_data.price_base_bdt} BDT, have {user.balance_bdt} BDT"
        )

    # Get color based on biome
    try:
        biome_enum = Biome(claim_data.biome.lower())
    except ValueError:
        biome_enum = Biome.PLAINS  # Default fallback

    # Map biome to color
    biome_colors = {
        Biome.OCEAN: "#1A5490",
        Biome.BEACH: "#e8bd88",
        Biome.PLAINS: "#7ba62a",
        Biome.FOREST: "#2d5016",
        Biome.DESERT: "#d4a26e",
        Biome.MOUNTAIN: "#6b7280",
        Biome.SNOW: "#f0f0f0"
    }
    color_hex = biome_colors.get(biome_enum, "#7ba62a")

    # Create new land
    new_land = Land(
        owner_id=user_id,
        x=claim_data.x,
        y=claim_data.y,
        z=0,
        biome=biome_enum,
        elevation=claim_data.elevation,
        color_hex=color_hex,
        price_base_bdt=claim_data.price_base_bdt,
        for_sale=False,
        fenced=False
    )

    # Deduct cost from user balance
    user.balance_bdt -= claim_data.price_base_bdt

    db.add(new_land)
    await db.commit()
    await db.refresh(new_land)

    # Invalidate caches
    await cache_service.delete(f"user_lands:{user_id}")

    logger.info(f"Land claimed at ({claim_data.x}, {claim_data.y}) by user {user_id} for {claim_data.price_base_bdt} BDT")

    # Return serialized land
    return await _serialize_land(new_land, db)


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
                Land.y.between(land.y - radius, land.y + radius)
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
