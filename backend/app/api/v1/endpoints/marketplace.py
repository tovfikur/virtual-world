"""
Marketplace Endpoints
Listing creation, bidding, and purchase operations
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import Optional
import logging
import uuid
from datetime import datetime

from app.db.session import get_db
from app.models.listing import Listing, ListingType, ListingStatus
from app.models.bid import Bid
from app.models.land import Land, Biome
from app.models.user import User
from app.schemas.listing_schema import (
    ListingCreate,
    ListingResponse,
    BidCreate,
    BidResponse,
    BuyNowRequest
)
from app.dependencies import get_current_user
from app.services.marketplace_service import marketplace_service
from app.services.cache_service import cache_service
from app.config import CACHE_TTLS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.post("/listings", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    listing_data: ListingCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new marketplace listing.

    Listing Types:
    - **auction**: Auction with starting price and duration
    - **fixed_price**: Fixed price with buy now only
    - **auction_with_buynow**: Auction with optional instant buy now

    Returns created listing with ID and status.
    """
    try:
        land_uuid = uuid.UUID(listing_data.land_id)
        seller_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    try:
        listing = await marketplace_service.create_listing(
            db=db,
            land_id=land_uuid,
            seller_id=seller_uuid,
            listing_type=ListingType(listing_data.listing_type),
            starting_price_bdt=listing_data.starting_price_bdt,
            reserve_price_bdt=listing_data.reserve_price_bdt,
            buy_now_price_bdt=listing_data.buy_now_price_bdt,
            duration_hours=listing_data.duration_hours,
            auto_extend_minutes=listing_data.auto_extend_minutes
        )

        # Build response with seller info
        listing_dict = listing.to_dict()
        listing_dict["seller_username"] = current_user.get("username")

        return ListingResponse(**listing_dict)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create listing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create listing"
        )


@router.get("/listings", response_model=dict)
async def search_listings(
    status_filter: Optional[str] = Query(None, alias="status"),
    listing_type: Optional[str] = Query(None),
    min_price_bdt: Optional[int] = Query(None, ge=0),
    max_price_bdt: Optional[int] = Query(None, ge=0),
    biome: Optional[str] = Query(None),
    seller_id: Optional[str] = Query(None),
    sort_by: str = Query("created_at_desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Search and filter marketplace listings.

    Supports:
    - Filtering by status, type, price range, biome, seller
    - Multiple sorting options
    - Pagination

    Sort options:
    - price_asc, price_desc
    - created_at_asc, created_at_desc
    - ending_soon (auctions ending soonest first)
    """
    # Build query with joins to get land info
    query = select(Listing, Land, User).join(
        Land, Listing.land_id == Land.land_id
    ).join(
        User, Listing.seller_id == User.user_id
    )

    # Apply filters
    if status_filter:
        try:
            status_enum = ListingStatus(status_filter)
            query = query.where(Listing.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.value for s in ListingStatus]}"
            )

    if listing_type:
        try:
            type_enum = ListingType(listing_type)
            query = query.where(Listing.listing_type == type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid listing type. Must be one of: {[t.value for t in ListingType]}"
            )

    if min_price_bdt is not None:
        query = query.where(Listing.current_price_bdt >= min_price_bdt)

    if max_price_bdt is not None:
        query = query.where(Listing.current_price_bdt <= max_price_bdt)

    if biome:
        try:
            biome_enum = Biome(biome)
            query = query.where(Land.biome == biome_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid biome. Must be one of: {[b.value for b in Biome]}"
            )

    if seller_id:
        try:
            seller_uuid = uuid.UUID(seller_id)
            query = query.where(Listing.seller_id == seller_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid seller ID format"
            )

    # Apply sorting
    if sort_by == "price_asc":
        query = query.order_by(Listing.current_price_bdt.asc())
    elif sort_by == "price_desc":
        query = query.order_by(Listing.current_price_bdt.desc())
    elif sort_by == "created_at_asc":
        query = query.order_by(Listing.created_at.asc())
    elif sort_by == "ending_soon":
        query = query.where(Listing.ends_at.isnot(None))
        query = query.order_by(Listing.ends_at.asc())
    else:  # created_at_desc
        query = query.order_by(Listing.created_at.desc())

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    # Build response with enriched data
    listings_data = []
    for listing, land, seller in rows:
        listing_dict = listing.to_dict()
        listing_dict["seller_username"] = seller.username
        listing_dict["land_x"] = land.x
        listing_dict["land_y"] = land.y
        listing_dict["land_biome"] = land.biome.value
        listings_data.append(listing_dict)

    return {
        "data": listings_data,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if total > 0 else 0,
            "has_next": page * limit < total,
            "has_prev": page > 1
        }
    }


@router.get("/listings/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific listing.
    """
    # Check cache
    cache_key = f"listing:{listing_id}"
    cached_listing = await cache_service.get(cache_key)

    if cached_listing:
        return ListingResponse(**cached_listing)

    try:
        listing_uuid = uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid listing ID format"
        )

    result = await db.execute(
        select(Listing, Land, User).join(
            Land, Listing.land_id == Land.land_id
        ).join(
            User, Listing.seller_id == User.user_id
        ).where(Listing.listing_id == listing_uuid)
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )

    listing, land, seller = row

    # Build response
    listing_dict = listing.to_dict()
    listing_dict["seller_username"] = seller.username
    listing_dict["land_x"] = land.x
    listing_dict["land_y"] = land.y
    listing_dict["land_biome"] = land.biome.value

    # Cache the result
    await cache_service.set(cache_key, listing_dict, ttl=CACHE_TTLS["listing"])

    return ListingResponse(**listing_dict)


@router.post("/listings/{listing_id}/bids", response_model=BidResponse, status_code=status.HTTP_201_CREATED)
async def place_bid(
    listing_id: str,
    bid_data: BidCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Place a bid on an auction listing.

    Requirements:
    - Listing must be an active auction
    - Bid must be higher than current price
    - Bidder must have sufficient balance
    - Cannot bid on own listing
    """
    try:
        listing_uuid = uuid.UUID(listing_id)
        bidder_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    try:
        bid = await marketplace_service.place_bid(
            db=db,
            listing_id=listing_uuid,
            bidder_id=bidder_uuid,
            amount_bdt=bid_data.amount_bdt
        )

        bid_dict = bid.to_dict()
        bid_dict["bidder_username"] = current_user.get("username")

        return BidResponse(**bid_dict)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to place bid: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to place bid"
        )


@router.get("/listings/{listing_id}/bids", response_model=dict)
async def get_listing_bids(
    listing_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all bids for a listing.

    Returns bids sorted by amount (highest first).
    """
    try:
        listing_uuid = uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid listing ID format"
        )

    # Verify listing exists
    result = await db.execute(
        select(Listing).where(Listing.listing_id == listing_uuid)
    )
    listing = result.scalar_one_or_none()

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )

    # Get total count
    count_result = await db.execute(
        select(func.count(Bid.bid_id)).where(Bid.listing_id == listing_uuid)
    )
    total = count_result.scalar()

    # Get bids with pagination
    offset = (page - 1) * limit
    result = await db.execute(
        select(Bid, User).join(
            User, Bid.bidder_id == User.user_id
        ).where(Bid.listing_id == listing_uuid)
        .order_by(Bid.amount_bdt.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()

    bids_data = []
    for bid, bidder in rows:
        bid_dict = bid.to_dict()
        bid_dict["bidder_username"] = bidder.username
        bids_data.append(bid_dict)

    return {
        "data": bids_data,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if total > 0 else 0,
            "has_next": page * limit < total,
            "has_prev": page > 1
        }
    }


@router.post("/listings/{listing_id}/buy-now", status_code=status.HTTP_200_OK)
async def buy_now(
    listing_id: str,
    buy_request: BuyNowRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute instant purchase via buy now.

    Payment Methods:
    - **balance**: Use BDT balance (instant)
    - **bkash/nagad/rocket/sslcommerz**: External gateway (requires confirmation)

    For balance payments, transaction is instant.
    For gateway payments, returns payment URL.
    """
    try:
        listing_uuid = uuid.UUID(listing_id)
        buyer_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    # Only balance payment supported for now
    if buy_request.payment_method != "balance":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Only balance payment supported in current version"
        )

    try:
        transaction = await marketplace_service.buy_now(
            db=db,
            listing_id=listing_uuid,
            buyer_id=buyer_uuid
        )

        return {
            "transaction_id": str(transaction.transaction_id),
            "listing_id": str(transaction.listing_id),
            "land_id": str(transaction.land_id),
            "amount_bdt": transaction.amount_bdt,
            "status": transaction.status.value,
            "payment_method": buy_request.payment_method,
            "completed_at": transaction.created_at.isoformat(),
            "message": "Purchase successful! Land ownership transferred."
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to execute buy now: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete purchase"
        )


@router.delete("/listings/{listing_id}", status_code=status.HTTP_200_OK)
async def cancel_listing(
    listing_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel an active listing.

    Requirements:
    - Listing must be active
    - Only seller can cancel
    - Cannot cancel if there are bids
    """
    try:
        listing_uuid = uuid.UUID(listing_id)
        seller_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    try:
        listing = await marketplace_service.cancel_listing(
            db=db,
            listing_id=listing_uuid,
            seller_id=seller_uuid
        )

        return {
            "listing_id": str(listing.listing_id),
            "status": listing.status.value,
            "cancelled_at": listing.updated_at.isoformat(),
            "message": "Listing cancelled successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to cancel listing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel listing"
        )


@router.get("/leaderboard/richest")
async def get_richest_leaderboard(
    limit: int = Query(100, ge=10, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """
    Get leaderboard of richest players by BDT balance.

    Returns top players ranked by balance.
    """
    # Check cache
    cache_key = f"leaderboard:richest:{limit}"
    cached_data = await cache_service.get(cache_key)

    if cached_data:
        return cached_data

    result = await db.execute(
        select(User)
        .order_by(User.balance_bdt.desc())
        .limit(limit)
    )
    users = result.scalars().all()

    leaderboard = []
    for rank, user in enumerate(users, 1):
        leaderboard.append({
            "rank": rank,
            "user_id": str(user.user_id),
            "username": user.username,
            "balance_bdt": user.balance_bdt,
            "role": user.role.value
        })

    response = {
        "leaderboard": leaderboard,
        "total_entries": len(leaderboard),
        "generated_at": datetime.utcnow().isoformat()
    }

    # Cache for 30 minutes
    await cache_service.set(cache_key, response, ttl=CACHE_TTLS["leaderboard"])

    return response


@router.get("/leaderboard/landowners")
async def get_landowners_leaderboard(
    limit: int = Query(100, ge=10, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """
    Get leaderboard of largest landowners.

    Returns top players ranked by number of lands owned.
    """
    # Check cache
    cache_key = f"leaderboard:landowners:{limit}"
    cached_data = await cache_service.get(cache_key)

    if cached_data:
        return cached_data

    # Get land counts per user
    result = await db.execute(
        select(
            User,
            func.count(Land.land_id).label("land_count")
        )
        .join(Land, User.user_id == Land.owner_id)
        .group_by(User.user_id)
        .order_by(func.count(Land.land_id).desc())
        .limit(limit)
    )
    rows = result.all()

    leaderboard = []
    for rank, (user, land_count) in enumerate(rows, 1):
        leaderboard.append({
            "rank": rank,
            "user_id": str(user.user_id),
            "username": user.username,
            "lands_owned": land_count
        })

    response = {
        "leaderboard": leaderboard,
        "total_entries": len(leaderboard),
        "generated_at": datetime.utcnow().isoformat()
    }

    # Cache for 30 minutes
    await cache_service.set(cache_key, response, ttl=CACHE_TTLS["leaderboard"])

    return response
