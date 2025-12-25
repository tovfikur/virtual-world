"""
Marketplace Service
Handles listing creation, bidding, and auction finalization
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import uuid
import logging

from app.models.listing import Listing, ListingType, ListingStatus
from app.models.listing_land import ListingLand
from app.models.bid import Bid, BidStatus
from app.models.land import Land
from app.models.user import User
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.admin_config import AdminConfig
from app.services.cache_service import cache_service
from app.services.parcel_service import parcel_service
from app.config import CACHE_TTLS

logger = logging.getLogger(__name__)


class MarketplaceService:
    """Service for marketplace operations."""

    @staticmethod
    async def create_listing(
        db: AsyncSession,
        land_ids: List[uuid.UUID],
        seller_id: uuid.UUID,
        listing_type: ListingType,
        starting_price_bdt: Optional[int] = None,
        reserve_price_bdt: Optional[int] = None,
        buy_now_price_bdt: Optional[int] = None,
        duration_hours: Optional[int] = None,
        auto_extend_minutes: int = 5
    ) -> Listing:
        """
        Create a new marketplace listing for a parcel.

        Args:
            db: Database session
            land_ids: List of land UUIDs in parcel (must be connected)
            seller_id: Seller user ID
            listing_type: Type of listing
            starting_price_bdt: Starting price for auction (for entire parcel)
            reserve_price_bdt: Reserve price for auction
            buy_now_price_bdt: Buy now price (for entire parcel)
            duration_hours: Auction duration
            auto_extend_minutes: Auto-extend on late bids

        Returns:
            Created listing

        Raises:
            ValueError: If validation fails
        """
        # Fetch all lands
        result = await db.execute(
            select(Land).where(Land.land_id.in_(land_ids))
        )
        lands = result.scalars().all()

        if len(lands) != len(land_ids):
            raise ValueError(f"Some lands not found (expected {len(land_ids)}, found {len(lands)})")

        # Verify all lands are owned by seller
        for land in lands:
            if land.owner_id != seller_id:
                raise ValueError(f"You can only list your own lands (land at {land.x},{land.y} not owned)")

        # Check if any land is already listed
        for land in lands:
            existing = await db.execute(
                select(ListingLand).where(
                    ListingLand.land_id == land.land_id
                ).join(Listing).where(Listing.status == ListingStatus.ACTIVE)
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Land at ({land.x},{land.y}) is already in an active listing")

        # Validate connectivity (lands must be edge-connected)
        land_coords = [(land.x, land.y) for land in lands]
        if not parcel_service.validate_connectivity(land_coords):
            raise ValueError("Lands must be connected (edge-adjacent, no diagonal-only connections)")

        # Validate auction duration against admin-configured limits
        if listing_type in [ListingType.AUCTION, ListingType.AUCTION_WITH_BUYNOW]:
            # Fetch AdminConfig
            cfg_res = await db.execute(select(AdminConfig).limit(1))
            config = cfg_res.scalar_one_or_none()
            min_hours = int(config.auction_min_duration_hours) if config else 1
            max_hours = int(config.auction_max_duration_hours) if config else 168

            if duration_hours is None:
                duration_hours = max(min_hours, 24)  # default to 24h within bounds
            if duration_hours < min_hours:
                raise ValueError(f"Auction duration must be at least {min_hours} hours")
            if duration_hours > max_hours:
                raise ValueError(f"Auction duration must be at most {max_hours} hours")

        # Calculate end time for auctions
        ends_at = None
        if listing_type in [ListingType.AUCTION, ListingType.AUCTION_WITH_BUYNOW]:
            ends_at = datetime.utcnow() + timedelta(hours=duration_hours)

        # Create listing
        listing = Listing(
            seller_id=seller_id,
            type=listing_type,
            price_bdt=starting_price_bdt or buy_now_price_bdt,
            reserve_price_bdt=reserve_price_bdt,
            buy_now_price_bdt=buy_now_price_bdt,
            auction_end_time=ends_at,
            auto_extend=(listing_type in [ListingType.AUCTION, ListingType.AUCTION_WITH_BUYNOW]),
            auto_extend_minutes=auto_extend_minutes
        )

        db.add(listing)
        await db.flush()  # Get listing_id

        # Create ListingLand records for each land in parcel
        for land in lands:
            listing_land = ListingLand(
                listing_id=listing.listing_id,
                land_id=land.land_id
            )
            db.add(listing_land)

            # Mark land as for sale
            land.for_sale = True

        await db.commit()
        await db.refresh(listing)

        # Invalidate caches
        for land in lands:
            await cache_service.delete(f"land:{land.land_id}")
        await cache_service.delete(f"active_listings")

        logger.info(f"Parcel listing created: {listing.listing_id} with {len(lands)} lands")

        return listing

    @staticmethod
    async def place_bid(
        db: AsyncSession,
        listing_id: uuid.UUID,
        bidder_id: uuid.UUID,
        amount_bdt: int
    ) -> Bid:
        """
        Place a bid on an auction listing.

        Args:
            db: Database session
            listing_id: Listing to bid on
            bidder_id: Bidder user ID
            amount_bdt: Bid amount

        Returns:
            Created bid

        Raises:
            ValueError: If validation fails
        """
        # Get listing
        result = await db.execute(
            select(Listing).where(Listing.listing_id == listing_id)
        )
        listing = result.scalar_one_or_none()

        if not listing:
            raise ValueError("Listing not found")

        if listing.status != ListingStatus.ACTIVE:
            raise ValueError("Listing is not active")

        if listing.type == ListingType.FIXED_PRICE:
            raise ValueError("Cannot bid on fixed price listings")

        # Check if auction has ended
        if listing.ends_at and listing.ends_at < datetime.utcnow():
            raise ValueError("Auction has ended")

        # Cannot bid on own listing
        if listing.seller_id == bidder_id:
            raise ValueError("Cannot bid on your own listing")

        # Validate bid amount
        # Fetch AdminConfig for minimum bid increment
        cfg_res = await db.execute(select(AdminConfig).limit(1))
        config = cfg_res.scalar_one_or_none()
        increment = int(config.auction_bid_increment) if config and config.auction_bid_increment is not None else 1
        current_price = listing.current_price_bdt if listing.current_price_bdt is not None else (listing.price_bdt or 0)
        min_bid = current_price + increment
        if amount_bdt < min_bid:
            raise ValueError(f"Bid must be at least {min_bid} BDT (increment {increment})")

        # Check bidder has sufficient balance
        result = await db.execute(
            select(User).where(User.user_id == bidder_id).with_for_update()
        )
        bidder = result.scalar_one_or_none()

        if not bidder:
            raise ValueError("Bidder not found")

        if bidder.balance_bdt < amount_bdt:
            raise ValueError("Insufficient balance")

        # Create bid
        bid = Bid(
            listing_id=listing_id,
            bidder_id=bidder_id,
            amount_bdt=amount_bdt
        )

        db.add(bid)

        # Update listing
        listing.current_price_bdt = amount_bdt
        listing.bid_count += 1
        listing.highest_bidder_id = bidder_id

        # Auto-extend if bid placed near end time
        if listing.ends_at and listing.auto_extend_minutes:
            time_remaining = (listing.ends_at - datetime.utcnow()).total_seconds() / 60
            if time_remaining < listing.auto_extend_minutes:
                listing.ends_at = datetime.utcnow() + timedelta(
                    minutes=listing.auto_extend_minutes
                )
                logger.info(f"Auction auto-extended: {listing_id}")

        await db.commit()
        await db.refresh(bid)

        # Invalidate cache
        await cache_service.delete(f"listing:{listing_id}")

        logger.info(f"Bid placed: {bid.bid_id} on listing {listing_id} for {amount_bdt} BDT")

        return bid

    @staticmethod
    async def buy_now(
        db: AsyncSession,
        listing_id: uuid.UUID,
        buyer_id: uuid.UUID
    ) -> Transaction:
        """
        Execute instant buy now purchase.

        Args:
            db: Database session
            listing_id: Listing to purchase
            buyer_id: Buyer user ID

        Returns:
            Transaction record

        Raises:
            ValueError: If validation fails
        """
        # Get listing
        result = await db.execute(
            select(Listing).where(Listing.listing_id == listing_id)
        )
        listing = result.scalar_one_or_none()

        if not listing:
            raise ValueError("Listing not found")

        if listing.status != ListingStatus.ACTIVE:
            raise ValueError("Listing is not active")

        if not listing.buy_now_price_bdt:
            raise ValueError("Buy now not available for this listing")

        # Cannot buy own listing
        if listing.seller_id == buyer_id:
            raise ValueError("Cannot buy your own listing")

        # Get buyer and seller
        result = await db.execute(
            select(User).where(User.user_id == buyer_id).with_for_update()
        )
        buyer = result.scalar_one_or_none()

        if not buyer:
            raise ValueError("Buyer not found")

        if buyer.balance_bdt < listing.buy_now_price_bdt:
            raise ValueError("Insufficient balance")

        result = await db.execute(
            select(User).where(User.user_id == listing.seller_id).with_for_update()
        )
        seller = result.scalar_one_or_none()

        # Get all lands in the parcel
        result = await db.execute(
            select(Land).join(ListingLand).where(
                ListingLand.listing_id == listing_id
            )
        )
        lands = result.scalars().all()

        if not lands:
            raise ValueError("No lands found in listing")

        # Execute transaction (apply tiered platform fee)
        amount = listing.buy_now_price_bdt

        # Fetch admin config for fee tiers
        cfg_res = await db.execute(select(AdminConfig).limit(1))
        config = cfg_res.scalar_one_or_none()

        def get_fee_percent(amount_bdt: int) -> float:
            if not config:
                return 5.0
            if amount_bdt < config.fee_tier_1_threshold:
                return float(config.fee_tier_1_percent)
            if amount_bdt < config.fee_tier_2_threshold:
                return float(config.fee_tier_2_percent)
            if amount_bdt < config.fee_tier_3_threshold:
                return float(config.fee_tier_3_percent)
            # Above highest threshold, use tier 3 percent
            return float(config.fee_tier_3_percent)

        fee_percent = get_fee_percent(amount)
        platform_fee = int(amount * (fee_percent / 100.0))

        buyer.balance_bdt -= amount
        seller.balance_bdt += (amount - platform_fee)

        # Transfer all lands in parcel to buyer
        for land in lands:
            land.owner_id = buyer_id
            land.for_sale = False
            land.fenced = False
            land.passcode_hash = None

        # Create transaction record (with land_count for parcel)
        transaction = Transaction(
            listing_id=listing_id,
            land_id=lands[0].land_id if lands else None,  # Primary land for legacy compat
            buyer_id=buyer_id,
            seller_id=listing.seller_id,
            amount_bdt=amount,
            transaction_type=TransactionType.BUY_NOW,
            status=TransactionStatus.COMPLETED
        )

        # Record platform fee
        transaction.platform_fee_bdt = platform_fee

        db.add(transaction)

        # Mark listing as sold
        listing.status = ListingStatus.SOLD

        await db.commit()
        await db.refresh(transaction)

        # Invalidate caches
        await cache_service.delete(f"listing:{listing_id}")
        for land in lands:
            await cache_service.delete(f"land:{land.land_id}")
        await cache_service.delete(f"user:{buyer_id}")
        await cache_service.delete(f"user:{seller.user_id}")

        logger.info(
            f"Buy now completed: listing {listing_id}, "
            f"buyer {buyer_id}, {len(lands)} lands, amount {listing.buy_now_price_bdt} BDT"
        )

        return transaction

    @staticmethod
    async def finalize_auction(
        db: AsyncSession,
        listing_id: uuid.UUID
    ) -> Optional[Transaction]:
        """
        Finalize an ended auction.

        Args:
            db: Database session
            listing_id: Listing to finalize

        Returns:
            Transaction record if sale occurred, None if reserve not met

        Raises:
            ValueError: If validation fails
        """
        # Get listing
        result = await db.execute(
            select(Listing).where(Listing.listing_id == listing_id)
        )
        listing = result.scalar_one_or_none()

        if not listing:
            raise ValueError("Listing not found")

        if listing.status != ListingStatus.ACTIVE:
            raise ValueError("Listing is not active")

        if not listing.ends_at or listing.ends_at > datetime.utcnow():
            raise ValueError("Auction has not ended yet")

        # Check if reserve price met
        if listing.reserve_price_bdt and listing.current_price_bdt < listing.reserve_price_bdt:
            # Reserve not met
            listing.status = ListingStatus.EXPIRED
            await db.commit()

            # Return land to not for sale
            # Get all lands in parcel
            result = await db.execute(
                select(Land).join(ListingLand).where(
                    ListingLand.listing_id == listing_id
                )
            )
            lands = result.scalars().all()
            for land in lands:
                land.for_sale = False
            await db.commit()

            logger.info(f"Auction expired (reserve not met): {listing_id}")
            return None

        if not listing.highest_bidder_id:
            # No bids
            listing.status = ListingStatus.EXPIRED
            await db.commit()

            # Get all lands in parcel
            result = await db.execute(
                select(Land).join(ListingLand).where(
                    ListingLand.listing_id == listing_id
                )
            )
            lands = result.scalars().all()
            for land in lands:
                land.for_sale = False
            await db.commit()

            logger.info(f"Auction expired (no bids): {listing_id}")
            return None

        # Get buyer and seller
        result = await db.execute(
            select(User).where(User.user_id == listing.highest_bidder_id).with_for_update()
        )
        buyer = result.scalar_one_or_none()

        result = await db.execute(
            select(User).where(User.user_id == listing.seller_id).with_for_update()
        )
        seller = result.scalar_one_or_none()

        # Get all lands in parcel
        result = await db.execute(
            select(Land).join(ListingLand).where(
                ListingLand.listing_id == listing_id
            )
        )
        lands = result.scalars().all()

        # Execute sale
        final_price = listing.current_price_bdt

        if buyer.balance_bdt < final_price:
            # Buyer has insufficient funds
            listing.status = ListingStatus.EXPIRED
            await db.commit()
            logger.warning(f"Auction failed (buyer insufficient funds): {listing_id}")
            return None

        # Transfer funds (apply tiered platform fee)
        # Fetch admin config for fee tiers
        cfg_res = await db.execute(select(AdminConfig).limit(1))
        config = cfg_res.scalar_one_or_none()

        def get_fee_percent(amount_bdt: int) -> float:
            if not config:
                return 5.0
            if amount_bdt < config.fee_tier_1_threshold:
                return float(config.fee_tier_1_percent)
            if amount_bdt < config.fee_tier_2_threshold:
                return float(config.fee_tier_2_percent)
            if amount_bdt < config.fee_tier_3_threshold:
                return float(config.fee_tier_3_percent)
            return float(config.fee_tier_3_percent)

        fee_percent = get_fee_percent(final_price)
        platform_fee = int(final_price * (fee_percent / 100.0))

        buyer.balance_bdt -= final_price
        seller.balance_bdt += (final_price - platform_fee)

        # Transfer all lands in parcel
        for land in lands:
            land.owner_id = buyer.user_id
            land.for_sale = False
            land.fenced = False
            land.passcode_hash = None

        # Create transaction
        transaction = Transaction(
            listing_id=listing_id,
            land_id=lands[0].land_id if lands else None,  # Primary land for legacy compat
            buyer_id=buyer.user_id,
            seller_id=seller.user_id,
            amount_bdt=final_price,
            transaction_type=TransactionType.AUCTION,
            status=TransactionStatus.COMPLETED
        )

        transaction.platform_fee_bdt = platform_fee

        db.add(transaction)

        # Mark listing as sold
        listing.status = ListingStatus.SOLD

        await db.commit()
        await db.refresh(transaction)

        # Invalidate caches
        await cache_service.delete(f"listing:{listing_id}")
        for land in lands:
            await cache_service.delete(f"land:{land.land_id}")

        logger.info(
            f"Auction finalized: listing {listing_id}, "
            f"buyer {buyer.user_id}, amount {final_price} BDT"
        )

        return transaction

    @staticmethod
    async def cancel_listing(
        db: AsyncSession,
        listing_id: uuid.UUID,
        seller_id: uuid.UUID
    ) -> Listing:
        """
        Cancel an active listing.

        Args:
            db: Database session
            listing_id: Listing to cancel
            seller_id: Seller user ID (for authorization)

        Returns:
            Updated listing

        Raises:
            ValueError: If validation fails
        """
        result = await db.execute(
            select(Listing).where(Listing.listing_id == listing_id)
        )
        listing = result.scalar_one_or_none()

        if not listing:
            raise ValueError("Listing not found")

        if listing.seller_id != seller_id:
            raise ValueError("Only seller can cancel listing")

        if listing.status != ListingStatus.ACTIVE:
            raise ValueError("Listing is not active")

        # Cannot cancel if there are bids
        if listing.bid_count > 0:
            raise ValueError("Cannot cancel listing with bids")

        listing.status = ListingStatus.CANCELLED

        # Mark all lands in parcel as not for sale
        result = await db.execute(
            select(Land).join(ListingLand).where(
                ListingLand.listing_id == listing_id
            )
        )
        lands = result.scalars().all()
        for land in lands:
            land.for_sale = False

        await db.commit()
        await db.refresh(listing)

        await cache_service.delete(f"listing:{listing_id}")
        for land in lands:
            await cache_service.delete(f"land:{land.land_id}")

        logger.info(f"Parcel listing cancelled: {listing_id} with {len(lands)} lands")

        return listing


# Global instance
marketplace_service = MarketplaceService()
