"""
Marketplace Endpoints
Listing creation, bidding, and purchase operations
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import Optional
import logging
import uuid
from datetime import datetime

from app.db.session import get_db
from app.models.listing import Listing, ListingType, ListingStatus
from app.models.listing_land import ListingLand
from app.models.bid import Bid
from app.models.land import Land, Biome
from app.models.user import User
from app.models.admin_config import AdminConfig
from app.schemas.listing_schema import (
    ListingCreate,
    ListingResponse,
    BidCreate,
    BidResponse,
    BuyNowRequest
)
from app.dependencies import get_current_user
from app.services.marketplace_service import marketplace_service
from app.services.parcel_service import parcel_service
from app.services.cache_service import cache_service
from app.services.rate_limit_service import rate_limit_service
from app.config import CACHE_TTLS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/marketplace", tags=["marketplace"])


def _rate_limit_identifier(request: Request, current_user: Optional[dict]) -> str:
    if current_user and current_user.get("sub"):
        return str(current_user["sub"])
    if request.client:
        return request.client.host
    return "anonymous"


async def _enforce_marketplace_rate_limit(
    db: AsyncSession,
    request: Request,
    current_user: Optional[dict]
):
    cfg_res = await db.execute(select(AdminConfig).limit(1))
    config = cfg_res.scalar_one_or_none()
    limit = config.marketplace_actions_per_hour if config else None
    if not limit:
        return

    identifier = _rate_limit_identifier(request, current_user)
    result = await rate_limit_service.check(
        bucket="marketplace",
        identifier=identifier,
        limit=limit,
        window_seconds=3600
    )
    if result and not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Marketplace rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": str(result.remaining),
                "X-RateLimit-Reset": str(result.reset_epoch),
            },
        )


@router.post("/listings", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    listing_data: ListingCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """
    Create a new marketplace listing for a parcel (one or more connected lands).

    **Parcel Requirements:**
    - All lands must be owned by you
    - Lands must be edge-connected (no diagonal-only connections)
    - No land can be in another active listing

    **Listing Types:**
    - **auction**: Auction with starting price and duration
    - **fixed_price**: Fixed price with buy now only
    - **auction_with_buynow**: Auction with optional instant buy now

    Returns created listing with parcel details.
    """
    try:
        land_uuids = [uuid.UUID(land_id) for land_id in listing_data.land_ids]
        seller_uuid = uuid.UUID(current_user["sub"])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format"
        )

    try:
        await _enforce_marketplace_rate_limit(db, request, current_user)

        listing = await marketplace_service.create_listing(
            db=db,
            land_ids=land_uuids,
            seller_id=seller_uuid,
            listing_type=ListingType(listing_data.listing_type),
            starting_price_bdt=listing_data.starting_price_bdt,
            reserve_price_bdt=listing_data.reserve_price_bdt,
            buy_now_price_bdt=listing_data.buy_now_price_bdt,
            duration_hours=listing_data.duration_hours,
            auto_extend_minutes=listing_data.auto_extend_minutes
        )

        # Get lands in parcel for response
        result = await db.execute(
            select(Land).join(ListingLand).where(
                ListingLand.listing_id == listing.listing_id
            )
        )
        lands = result.scalars().all()

        # Build response with parcel data
        listing_dict = listing.to_dict()
        listing_dict["seller_username"] = current_user.get("username")
        listing_dict["land_count"] = len(lands)
        listing_dict["lands"] = [
            {
                "land_id": str(land.land_id),
                "x": land.x,
                "y": land.y,
                "biome": land.biome.value
            }
            for land in lands
        ]
        listing_dict["bounding_box"] = parcel_service.calculate_bounding_box(
            [(land.x, land.y) for land in lands]
        )
        listing_dict["biomes"] = list(set(land.biome.value for land in lands))

        return ListingResponse(**listing_dict)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create parcel listing: {e}")
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
    Search and filter marketplace parcel listings.

    Supports:
    - Filtering by status, type, price range, biome, seller
    - Multiple sorting options
    - Pagination

    Sort options:
    - price_asc, price_desc
    - created_at_asc, created_at_desc
    - ending_soon (auctions ending soonest first)
    """
    # Build base query - listings with seller info
    query = select(Listing).join(
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
            query = query.where(Listing.type == type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid listing type. Must be one of: {[t.value for t in ListingType]}"
            )

    if min_price_bdt is not None:
        query = query.where(Listing.price_bdt >= min_price_bdt)

    if max_price_bdt is not None:
        query = query.where(Listing.price_bdt <= max_price_bdt)

    if biome:
        # Filter parcels that contain the specified biome
        try:
            biome_enum = Biome(biome)
            query = query.join(ListingLand).join(Land).where(Land.biome == biome_enum)
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
        query = query.order_by(Listing.price_bdt.asc())
    elif sort_by == "price_desc":
        query = query.order_by(Listing.price_bdt.desc())
    elif sort_by == "created_at_asc":
        query = query.order_by(Listing.created_at.asc())
    elif sort_by == "ending_soon":
        query = query.where(Listing.auction_end_time.isnot(None))
        query = query.order_by(Listing.auction_end_time.asc())
    else:  # created_at_desc
        query = query.order_by(Listing.created_at.desc())

    # Get total count
    count_query = select(func.count(Listing.listing_id.distinct())).select_from(Listing)
    if status_filter:
        count_query = count_query.where(Listing.status == status_enum)
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    listings = result.scalars().all()

    # Build response with parcel data for each listing
    listings_data = []
    for listing in listings:
        # Get lands in this parcel
        lands_result = await db.execute(
            select(Land).join(ListingLand).where(
                ListingLand.listing_id == listing.listing_id
            )
        )
        lands = lands_result.scalars().all()

        # Get seller
        seller_result = await db.execute(
            select(User).where(User.user_id == listing.seller_id)
        )
        seller = seller_result.scalar_one_or_none()

        listing_dict = listing.to_dict()
        listing_dict["seller_username"] = seller.username if seller else None
        listing_dict["land_count"] = len(lands)
        listing_dict["lands"] = [
            {"x": land.x, "y": land.y, "biome": land.biome.value}
            for land in lands
        ]
        listing_dict["bounding_box"] = parcel_service.calculate_bounding_box(
            [(land.x, land.y) for land in lands]
        )
        listing_dict["biomes"] = list(set(land.biome.value for land in lands))
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
    Get detailed information about a specific parcel listing.

    Includes all lands in the parcel, bounding box, and unique biomes.
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

    # Get listing
    result = await db.execute(
        select(Listing).where(Listing.listing_id == listing_uuid)
    )
    listing = result.scalar_one_or_none()

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )

    # Get seller
    seller_result = await db.execute(
        select(User).where(User.user_id == listing.seller_id)
    )
    seller = seller_result.scalar_one_or_none()

    # Get all lands in parcel
    lands_result = await db.execute(
        select(Land).join(ListingLand).where(
            ListingLand.listing_id == listing_uuid
        )
    )
    lands = lands_result.scalars().all()

    # Build response with parcel data
    listing_dict = listing.to_dict()
    listing_dict["seller_username"] = seller.username if seller else None
    listing_dict["land_count"] = len(lands)
    listing_dict["lands"] = [
        {
            "land_id": str(land.land_id),
            "x": land.x,
            "y": land.y,
            "biome": land.biome.value,
            "elevation": land.elevation
        }
        for land in lands
    ]
    listing_dict["bounding_box"] = parcel_service.calculate_bounding_box(
        [(land.x, land.y) for land in lands]
    )
    listing_dict["biomes"] = list(set(land.biome.value for land in lands))

    # Cache the result
    await cache_service.set(cache_key, listing_dict, ttl=CACHE_TTLS["listing"])

    return ListingResponse(**listing_dict)


@router.post("/listings/{listing_id}/bids", response_model=BidResponse, status_code=status.HTTP_201_CREATED)
async def place_bid(
    listing_id: str,
    bid_data: BidCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None
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
        await _enforce_marketplace_rate_limit(db, request, current_user)

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
    db: AsyncSession = Depends(get_db),
    request: Request = None
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
        await _enforce_marketplace_rate_limit(db, request, current_user)

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


# =============================================================================
# Unified Transaction History
# =============================================================================

@router.get("/transactions/audit-trail", tags=["analytics"])
async def get_unified_audit_trail(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    transaction_source: Optional[str] = Query(None, description="Filter by: marketplace, biome, or wallet"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get unified audit trail of all transactions (marketplace + biome trading).
    
    Shows complete transaction history combining:
    - Land marketplace transactions (buy/sell/auction)
    - Biome share trading transactions
    - Wallet top-ups
    
    Each entry includes:
    - transaction_source: Type of transaction (marketplace, biome, wallet)
    - All transaction details (amount, fees, participants)
    - For biome trades: share quantity and price
    - For marketplace: land and listing info
    """
    try:
        user_uuid = uuid.UUID(current_user["sub"])
        
        # Build query for unified transactions
        from app.models.transaction import Transaction, TransactionType
        
        query = select(Transaction).where(
            or_(
                Transaction.buyer_id == user_uuid,
                Transaction.seller_id == user_uuid
            )
        )
        
        # Filter by transaction source if specified
        if transaction_source:
            if transaction_source == "biome":
                query = query.where(
                    Transaction.transaction_type.in_([
                        TransactionType.BIOME_BUY,
                        TransactionType.BIOME_SELL
                    ])
                )
            elif transaction_source == "marketplace":
                query = query.where(
                    Transaction.transaction_type.in_([
                        TransactionType.AUCTION,
                        TransactionType.BUY_NOW,
                        TransactionType.FIXED_PRICE,
                        TransactionType.TRANSFER
                    ])
                )
            elif transaction_source == "wallet":
                query = query.where(
                    Transaction.transaction_type == TransactionType.TOPUP
                )
        
        # Order by creation date (newest first) and apply pagination
        query = query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit)
        
        result = await db.execute(query)
        transactions = result.scalars().all()
        
        # Get total count for pagination
        count_result = await db.execute(
            select(func.count(Transaction.transaction_id)).where(
                or_(
                    Transaction.buyer_id == user_uuid,
                    Transaction.seller_id == user_uuid
                )
            )
        )
        total_count = count_result.scalar() or 0
        
        # Format response
        transactions_data = []
        for tx in transactions:
            tx_dict = tx.to_dict()
            
            # Add transaction source for easier filtering
            if tx.transaction_type.value.startswith("biome"):
                tx_dict["transaction_source"] = "biome"
            elif tx.transaction_type == TransactionType.TOPUP:
                tx_dict["transaction_source"] = "wallet"
            else:
                tx_dict["transaction_source"] = "marketplace"
            
            # Add user role context (was user buyer or seller)
            if tx.buyer_id == user_uuid:
                tx_dict["user_role"] = "buyer"
            elif tx.seller_id == user_uuid:
                tx_dict["user_role"] = "seller"
            else:
                tx_dict["user_role"] = "none"
            
            transactions_data.append(tx_dict)
        
        return {
            "transactions": transactions_data,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total": total_count,
                "returned": len(transactions_data)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to retrieve audit trail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transaction history"
        )

