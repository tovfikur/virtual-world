# Virtual Land World - Land Ownership API

## Land Management Endpoints

```python
# app/api/v1/endpoints/lands.py

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_
from typing import List, Optional
import logging

from app.db.session import get_db
from app.models.land import Land, Biome
from app.models.user import User
from app.dependencies import get_current_user
from app.services.land_service import land_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lands", tags=["lands"])

class LandResponse(BaseModel):
    land_id: str
    owner_id: str
    x: int
    y: int
    biome: str
    color_hex: str
    fenced: bool
    public_message: Optional[str]
    price_base_bdt: int
    for_sale: bool
    created_at: datetime

@router.get("/{land_id}")
async def get_land(
    land_id: str = Path(...),
    db: AsyncSession = Depends(get_db)
):
    """Get land details."""
    land = await db.query(Land).filter(Land.land_id == land_id).first()

    if not land:
        raise HTTPException(status_code=404, detail="Land not found")

    return {
        "land_id": str(land.land_id),
        "owner_id": str(land.owner_id),
        "coordinates": {"x": land.x, "y": land.y, "z": land.z},
        "biome": land.biome.value,
        "color_hex": land.color_hex,
        "elevation": land.elevation,
        "fenced": land.fenced,
        "passcode_required": land.passcode_hash is not None,
        "public_message": land.public_message,
        "price_base_bdt": land.price_base_bdt,
        "for_sale": land.for_sale,
        "created_at": land.created_at.isoformat()
    }

@router.get("/")
async def search_lands(
    biome: Optional[str] = Query(None),
    min_price_bdt: Optional[int] = Query(None),
    max_price_bdt: Optional[int] = Query(None),
    for_sale: Optional[bool] = Query(None),
    owner_id: Optional[str] = Query(None),
    x: Optional[int] = Query(None),
    y: Optional[int] = Query(None),
    radius: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("created_at_desc"),
    db: AsyncSession = Depends(get_db)
):
    """Search and filter lands."""
    query = db.query(Land).filter(Land.deleted_at.is_(None))

    # Apply filters
    if biome:
        query = query.filter(Land.biome == biome)
    if min_price_bdt:
        query = query.filter(Land.price_base_bdt >= min_price_bdt)
    if max_price_bdt:
        query = query.filter(Land.price_base_bdt <= max_price_bdt)
    if for_sale is not None:
        query = query.filter(Land.for_sale == for_sale)
    if owner_id:
        query = query.filter(Land.owner_id == owner_id)

    # Proximity search
    if x is not None and y is not None and radius:
        query = query.filter(
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
    else:
        query = query.order_by(Land.created_at.desc())

    # Pagination
    total = await db.execute(query.statement.with_only_columns(func.count()))
    total_count = total.scalar()

    offset = (page - 1) * limit
    lands = await query.offset(offset).limit(limit).all()

    return {
        "data": [
            {
                "land_id": str(land.land_id),
                "owner_id": str(land.owner_id),
                "coordinates": {"x": land.x, "y": land.y},
                "biome": land.biome.value,
                "color_hex": land.color_hex,
                "price_base_bdt": land.price_base_bdt,
                "for_sale": land.for_sale
            }
            for land in lands
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total_count,
            "pages": (total_count + limit - 1) // limit,
            "has_next": page * limit < total_count,
            "has_prev": page > 1
        }
    }

@router.post("/{land_id}/fence")
async def fence_land(
    land_id: str,
    fenced: bool,
    passcode: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Enable or disable land fencing."""
    land = await db.query(Land).filter(Land.land_id == land_id).first()

    if not land:
        raise HTTPException(status_code=404, detail="Land not found")

    # Verify ownership
    if land.owner_id != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    land.fenced = fenced

    if fenced and passcode:
        land.set_passcode(passcode)

    await db.commit()
    await db.refresh(land)

    logger.info(f"Land {land_id} fencing updated: {fenced}")

    return {
        "land_id": str(land.land_id),
        "fenced": land.fenced,
        "passcode_updated_at": land.passcode_updated_at.isoformat() if land.passcode_updated_at else None
    }

@router.post("/{land_id}/transfer")
async def transfer_land(
    land_id: str,
    new_owner_id: str,
    message: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Transfer land to another user."""
    land = await db.query(Land).filter(Land.land_id == land_id).first()

    if not land:
        raise HTTPException(status_code=404, detail="Land not found")

    # Verify ownership
    if str(land.owner_id) != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Verify new owner exists
    new_owner = await db.query(User).filter(User.user_id == new_owner_id).first()
    if not new_owner:
        raise HTTPException(status_code=404, detail="New owner not found")

    # Transfer
    previous_owner_id = land.owner_id
    land.owner_id = new_owner_id
    land.fenced = False
    land.passcode_hash = None

    await db.commit()
    await db.refresh(land)

    logger.info(f"Land transferred from {previous_owner_id} to {new_owner_id}")

    return {
        "land_id": str(land.land_id),
        "previous_owner_id": str(previous_owner_id),
        "new_owner_id": str(land.owner_id),
        "transfer_completed_at": datetime.utcnow().isoformat()
    }

@router.get("/{land_id}/heatmap")
async def get_land_heatmap(
    land_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get pricing heatmap for region around land."""
    land = await db.query(Land).filter(Land.land_id == land_id).first()

    if not land:
        raise HTTPException(status_code=404, detail="Land not found")

    # Find nearby lands within radius (e.g., 500m)
    nearby = await db.query(Land).filter(
        and_(
            Land.x.between(land.x - 10, land.x + 10),
            Land.y.between(land.y - 10, land.y + 10),
            Land.deleted_at.is_(None)
        )
    ).all()

    prices = [l.price_base_bdt for l in nearby]

    return {
        "center_land_id": str(land.land_id),
        "price_range": {
            "min_bdt": min(prices) if prices else 0,
            "max_bdt": max(prices) if prices else 0,
            "avg_bdt": sum(prices) // len(prices) if prices else 0
        },
        "nearby_lands": [
            {
                "land_id": str(l.land_id),
                "distance_m": max(abs(l.x - land.x), abs(l.y - land.y)) * 500,
                "price_bdt": l.price_base_bdt,
                "biome": l.biome.value
            }
            for l in nearby[:10]
        ],
        "generated_at": datetime.utcnow().isoformat()
    }
```

## Land Service

```python
# app/services/land_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_
from uuid import UUID
import logging

from app.models.land import Land, Biome

logger = logging.getLogger(__name__)

class LandService:
    """Land ownership and management logic."""

    async def get_user_lands(self, db: AsyncSession, user_id: UUID) -> list:
        """Get all lands owned by user."""
        lands = await db.query(Land).filter(
            and_(
                Land.owner_id == user_id,
                Land.deleted_at.is_(None)
            )
        ).all()
        return lands

    async def get_land_by_coordinates(
        self,
        db: AsyncSession,
        x: int, y: int, z: int = 0
    ) -> Optional[Land]:
        """Get land by coordinates."""
        land = await db.query(Land).filter(
            and_(
                Land.x == x,
                Land.y == y,
                Land.z == z
            )
        ).first()
        return land

    async def verify_access(
        self,
        db: AsyncSession,
        land_id: UUID,
        user_id: UUID,
        passcode: Optional[str] = None
    ) -> bool:
        """Verify user has access to land (for chat/calls)."""
        land = await db.query(Land).filter(Land.land_id == land_id).first()

        if not land:
            return False

        # Owner always has access
        if land.owner_id == user_id:
            return True

        # If not fenced, everyone has access
        if not land.fenced:
            return True

        # If fenced, need correct passcode
        if land.fenced and passcode:
            return land.verify_passcode(passcode)

        return False

    async def get_proximity_lands(
        self,
        db: AsyncSession,
        x: int, y: int,
        radius: int = 2
    ) -> list:
        """Get lands within proximity (for chat auto-join)."""
        lands = await db.query(Land).filter(
            and_(
                Land.x.between(x - radius, x + radius),
                Land.y.between(y - radius, y + radius),
                Land.deleted_at.is_(None)
            )
        ).all()
        return lands

# Global instance
land_service = LandService()
```

## Leaderboards

```python
@router.get("/leaderboard/richest")
async def get_richest_players(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get richest players by balance."""
    users = await db.query(User).order_by(
        User.balance_bdt.desc()
    ).limit(limit).all()

    return {
        "leaderboard": [
            {
                "rank": idx + 1,
                "username": user.username,
                "balance_bdt": user.balance_bdt
            }
            for idx, user in enumerate(users)
        ]
    }

@router.get("/leaderboard/most-valuable")
async def get_most_valuable_lands(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get most valuable land holdings by user."""
    query = db.query(
        User.username,
        func.sum(Land.price_base_bdt).label("total_value")
    ).join(Land).filter(
        Land.deleted_at.is_(None)
    ).group_by(User.user_id).order_by(
        func.sum(Land.price_base_bdt).desc()
    ).limit(limit)

    results = await query.all()

    return {
        "leaderboard": [
            {
                "rank": idx + 1,
                "username": username,
                "total_land_value_bdt": total_value
            }
            for idx, (username, total_value) in enumerate(results)
        ]
    }
```

**Resume Token:** `✓ PHASE_3_LAND_API_COMPLETE`
