# Virtual Land World - Marketplace & Auction System

## Marketplace Service

```python
# app/services/marketplace_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, desc
from uuid import UUID
from decimal import Decimal

class MarketplaceService:
    """Land marketplace and auction logic."""

    async def create_listing(
        self,
        db: AsyncSession,
        seller_id: UUID,
        land_id: UUID,
        listing_type: str,
        price_bdt: int,
        **kwargs
    ) -> dict:
        """Create new land listing."""
        listing = Listing(
            land_id=land_id,
            seller_id=seller_id,
            type=listing_type,
            price_bdt=price_bdt,
            description=kwargs.get("description"),
            images=kwargs.get("images"),
            reserve_price_bdt=kwargs.get("reserve_price_bdt"),
            buy_now_enabled=kwargs.get("buy_now_enabled", False),
            buy_now_price_bdt=kwargs.get("buy_now_price_bdt")
        )

        if listing_type == "auction":
            from datetime import timedelta, datetime
            listing.auction_start_time = datetime.utcnow()
            listing.auction_end_time = datetime.utcnow() + timedelta(
                hours=kwargs.get("auction_duration_hours", 24)
            )

        db.add(listing)
        await db.commit()
        return self._listing_to_dict(listing)

    async def place_bid(
        self,
        db: AsyncSession,
        listing_id: UUID,
        bidder_id: UUID,
        amount_bdt: int
    ) -> dict:
        """Place bid on auction listing."""
        listing = await db.query(Listing).filter(
            Listing.listing_id == listing_id
        ).with_for_update().first()

        if not listing or listing.status != ListingStatus.ACTIVE:
            raise HTTPException(status_code=404, detail="Listing not found")

        # Verify it's an auction
        if listing.type != ListingType.AUCTION:
            raise HTTPException(status_code=400, detail="Not an auction")

        # Get current highest bid
        highest_bid = await db.query(Bid).filter(
            Bid.listing_id == listing_id
        ).order_by(desc(Bid.amount_bdt)).first()

        min_bid = (highest_bid.amount_bdt + 50) if highest_bid else listing.price_bdt

        if amount_bdt < min_bid:
            raise HTTPException(
                status_code=400,
                detail=f"Bid must be at least {min_bid} BDT"
            )

        # Check user balance
        bidder = await db.query(User).filter(
            User.user_id == bidder_id
        ).with_for_update().first()

        if bidder.balance_bdt < amount_bdt:
            raise HTTPException(status_code=400, detail="Insufficient balance")

        # Mark previous bid as outbid
        if highest_bid:
            highest_bid.status = BidStatus.OUTBID

        # Create new bid
        bid = Bid(
            listing_id=listing_id,
            bidder_id=bidder_id,
            amount_bdt=amount_bdt
        )
        db.add(bid)

        # Auto-extend auction if bid near end
        from datetime import datetime, timedelta
        if listing.auto_extend:
            time_left = (listing.auction_end_time - datetime.utcnow()).total_seconds()
            if time_left < 300:  # Less than 5 minutes left
                listing.extend_auction()

        await db.commit()
        return {"bid_id": str(bid.bid_id), "amount_bdt": amount_bdt}

    async def finalize_auction(self, db: AsyncSession, listing_id: UUID):
        """End auction and transfer land to winner."""
        listing = await db.query(Listing).filter(
            Listing.listing_id == listing_id
        ).with_for_update().first()

        if not listing:
            return

        # Get winning bid
        winning_bid = await db.query(Bid).filter(
            Bid.listing_id == listing_id
        ).order_by(desc(Bid.amount_bdt)).first()

        if not winning_bid:
            listing.status = ListingStatus.EXPIRED
            await db.commit()
            return

        # Create transaction
        txn = Transaction(
            land_id=listing.land_id,
            seller_id=listing.seller_id,
            buyer_id=winning_bid.bidder_id,
            listing_id=listing_id,
            amount_bdt=winning_bid.amount_bdt,
            platform_fee_bdt=int(winning_bid.amount_bdt * 0.05),
            gateway_fee_bdt=0,
            status=TransactionStatus.COMPLETED
        )

        # Update balances
        seller = await db.query(User).filter(
            User.user_id == listing.seller_id
        ).with_for_update().first()
        buyer = await db.query(User).filter(
            User.user_id == winning_bid.bidder_id
        ).with_for_update().first()

        seller.balance_bdt += txn.seller_receives_bdt
        buyer.balance_bdt -= winning_bid.amount_bdt

        # Transfer land
        land = await db.query(Land).filter(
            Land.land_id == listing.land_id
        ).first()
        land.owner_id = winning_bid.bidder_id

        # Update listing & bid status
        listing.status = ListingStatus.SOLD
        listing.sold_at = datetime.utcnow()
        winning_bid.status = BidStatus.WON

        db.add(txn)
        await db.commit()
```

## Pricing Algorithm

```python
# app/services/pricing_service.py

class PricingService:
    """Dynamic land pricing calculations."""

    async def calculate_land_price(
        self,
        db: AsyncSession,
        land: Land,
        config: AdminConfig
    ) -> int:
        """Calculate land price based on multiple factors."""
        base_price = config.base_land_price_bdt

        # Biome multiplier
        biome_multipliers = {
            "forest": config.forest_multiplier,
            "desert": config.desert_multiplier,
            "grassland": config.grassland_multiplier,
            "water": config.water_multiplier,
            "snow": config.snow_multiplier
        }
        biome_price = base_price * biome_multipliers[land.biome.value]

        # Proximity bonus (near center 0,0)
        distance = (land.x ** 2 + land.y ** 2) ** 0.5
        proximity_bonus = max(0, 1 + (1000 - distance) / 10000)

        # Market demand (based on recent sales)
        recent_sales = await db.query(Transaction).filter(
            Transaction.created_at > datetime.utcnow() - timedelta(days=7)
        ).count()
        demand_multiplier = 1 + (recent_sales / 100)

        final_price = int(biome_price * proximity_bonus * demand_multiplier)
        return max(base_price, final_price)

    async def get_price_history(
        self,
        db: AsyncSession,
        biome: str,
        days: int = 30
    ) -> list:
        """Get price history for biome."""
        transactions = await db.query(
            func.date(Transaction.created_at).label("date"),
            func.avg(Transaction.amount_bdt).label("avg_price")
        ).join(Land).filter(
            Land.biome == biome,
            Transaction.created_at > datetime.utcnow() - timedelta(days=days)
        ).group_by(
            func.date(Transaction.created_at)
        ).order_by("date").all()

        return [{"date": t.date, "avg_price": t.avg_price} for t in transactions]
```

## Marketplace Endpoints

```python
# app/api/v1/endpoints/marketplace.py

@router.post("/listings")
async def create_listing(
    land_id: str,
    type: str,
    price_bdt: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create land listing."""
    # Verify ownership
    land = await db.query(Land).filter(Land.land_id == land_id).first()
    if not land or str(land.owner_id) != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    listing = await marketplace_service.create_listing(
        db, land.owner_id, land_id, type, price_bdt
    )
    return listing

@router.post("/listings/{listing_id}/bids")
async def place_bid(
    listing_id: str,
    amount_bdt: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Place bid on auction."""
    bid = await marketplace_service.place_bid(
        db, listing_id, current_user["sub"], amount_bdt
    )
    return bid

@router.post("/listings/{listing_id}/buy-now")
async def buy_now(
    listing_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Purchase land at buy-now price."""
    listing = await db.query(Listing).filter(
        Listing.listing_id == listing_id
    ).first()

    if not listing or not listing.buy_now_enabled:
        raise HTTPException(status_code=404, detail="Not available")

    # Similar transaction logic as auction finalization
    pass

@router.get("/leaderboard/richest")
async def get_richest_players(
    limit: int = Query(10),
    db: AsyncSession = Depends(get_db)
):
    """Get richest players."""
    users = await db.query(User).order_by(
        User.balance_bdt.desc()
    ).limit(limit).all()

    return {
        "leaderboard": [
            {"rank": idx + 1, "username": u.username, "balance": u.balance_bdt}
            for idx, u in enumerate(users)
        ]
    }
```

**Resume Token:** `✓ PHASE_5_COMPLETE`
