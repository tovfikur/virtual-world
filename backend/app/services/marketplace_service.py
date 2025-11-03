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
from app.models.bid import Bid, BidStatus
from app.models.land import Land
from app.models.user import User
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.services.cache_service import cache_service
from app.config import CACHE_TTLS

logger = logging.getLogger(__name__)


class MarketplaceService:
    """Service for marketplace operations."""

    @staticmethod
    async def create_listing(
        db: AsyncSession,
        land_id: uuid.UUID,
        seller_id: uuid.UUID,
        listing_type: ListingType,
        starting_price_bdt: Optional[int] = None,
        reserve_price_bdt: Optional[int] = None,
        buy_now_price_bdt: Optional[int] = None,
        duration_hours: Optional[int] = None,
        auto_extend_minutes: int = 5
    ) -> Listing:
        """
        Create a new marketplace listing.

        Args:
            db: Database session
            land_id: Land to list
            seller_id: Seller user ID
            listing_type: Type of listing
            starting_price_bdt: Starting price for auction
            reserve_price_bdt: Reserve price for auction
            buy_now_price_bdt: Buy now price
            duration_hours: Auction duration
            auto_extend_minutes: Auto-extend on late bids

        Returns:
            Created listing

        Raises:
            ValueError: If validation fails
        """
        # Verify land exists and is owned by seller
        result = await db.execute(
            select(Land).where(Land.land_id == land_id)
        )
        land = result.scalar_one_or_none()

        if not land:
            raise ValueError("Land not found")

        if land.owner_id != seller_id:
            raise ValueError("You can only list your own land")

        # Check if land is already listed
        existing_listing = await db.execute(
            select(Listing).where(
                and_(
                    Listing.land_id == land_id,
                    Listing.status == ListingStatus.ACTIVE
                )
            )
        )
        if existing_listing.scalar_one_or_none():
            raise ValueError("Land is already listed")

        # Calculate end time for auctions
        ends_at = None
        if listing_type in [ListingType.AUCTION, ListingType.AUCTION_WITH_BUYNOW]:
            ends_at = datetime.utcnow() + timedelta(hours=duration_hours)

        # Create listing
        listing = Listing(
            land_id=land_id,
            seller_id=seller_id,
            listing_type=listing_type,
            starting_price_bdt=starting_price_bdt,
            current_price_bdt=starting_price_bdt or buy_now_price_bdt,
            reserve_price_bdt=reserve_price_bdt,
            buy_now_price_bdt=buy_now_price_bdt,
            ends_at=ends_at,
            auto_extend_minutes=auto_extend_minutes
        )

        db.add(listing)
        await db.commit()
        await db.refresh(listing)

        # Mark land as for sale
        land.for_sale = True
        await db.commit()

        # Invalidate caches
        await cache_service.delete(f"land:{land_id}")
        await cache_service.delete(f"active_listings")

        logger.info(f"Listing created: {listing.listing_id} for land {land_id}")

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

        if listing.listing_type == ListingType.FIXED_PRICE:
            raise ValueError("Cannot bid on fixed price listings")

        # Check if auction has ended
        if listing.ends_at and listing.ends_at < datetime.utcnow():
            raise ValueError("Auction has ended")

        # Cannot bid on own listing
        if listing.seller_id == bidder_id:
            raise ValueError("Cannot bid on your own listing")

        # Validate bid amount
        min_bid = listing.current_price_bdt + 1  # Must be at least 1 BDT higher
        if amount_bdt < min_bid:
            raise ValueError(f"Bid must be at least {min_bid} BDT")

        # Check bidder has sufficient balance
        result = await db.execute(
            select(User).where(User.user_id == bidder_id)
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
            select(User).where(User.user_id == buyer_id)
        )
        buyer = result.scalar_one_or_none()

        if not buyer:
            raise ValueError("Buyer not found")

        if buyer.balance_bdt < listing.buy_now_price_bdt:
            raise ValueError("Insufficient balance")

        result = await db.execute(
            select(User).where(User.user_id == listing.seller_id)
        )
        seller = result.scalar_one_or_none()

        # Get land
        result = await db.execute(
            select(Land).where(Land.land_id == listing.land_id)
        )
        land = result.scalar_one_or_none()

        # Execute transaction
        buyer.balance_bdt -= listing.buy_now_price_bdt
        seller.balance_bdt += listing.buy_now_price_bdt

        # Transfer land ownership
        land.owner_id = buyer_id
        land.for_sale = False
        land.fenced = False
        land.passcode_hash = None

        # Create transaction record
        transaction = Transaction(
            listing_id=listing_id,
            land_id=listing.land_id,
            buyer_id=buyer_id,
            seller_id=listing.seller_id,
            amount_bdt=listing.buy_now_price_bdt,
            transaction_type=TransactionType.BUY_NOW,
            status=TransactionStatus.COMPLETED
        )

        db.add(transaction)

        # Mark listing as sold
        listing.status = ListingStatus.SOLD

        await db.commit()
        await db.refresh(transaction)

        # Invalidate caches
        await cache_service.delete(f"listing:{listing_id}")
        await cache_service.delete(f"land:{listing.land_id}")
        await cache_service.delete(f"user:{buyer_id}")
        await cache_service.delete(f"user:{seller.user_id}")

        logger.info(
            f"Buy now completed: listing {listing_id}, "
            f"buyer {buyer_id}, amount {listing.buy_now_price_bdt} BDT"
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
            result = await db.execute(
                select(Land).where(Land.land_id == listing.land_id)
            )
            land = result.scalar_one_or_none()
            if land:
                land.for_sale = False
                await db.commit()

            logger.info(f"Auction expired (reserve not met): {listing_id}")
            return None

        if not listing.highest_bidder_id:
            # No bids
            listing.status = ListingStatus.EXPIRED
            await db.commit()

            result = await db.execute(
                select(Land).where(Land.land_id == listing.land_id)
            )
            land = result.scalar_one_or_none()
            if land:
                land.for_sale = False
                await db.commit()

            logger.info(f"Auction expired (no bids): {listing_id}")
            return None

        # Get buyer and seller
        result = await db.execute(
            select(User).where(User.user_id == listing.highest_bidder_id)
        )
        buyer = result.scalar_one_or_none()

        result = await db.execute(
            select(User).where(User.user_id == listing.seller_id)
        )
        seller = result.scalar_one_or_none()

        result = await db.execute(
            select(Land).where(Land.land_id == listing.land_id)
        )
        land = result.scalar_one_or_none()

        # Execute sale
        final_price = listing.current_price_bdt

        if buyer.balance_bdt < final_price:
            # Buyer has insufficient funds
            listing.status = ListingStatus.EXPIRED
            await db.commit()
            logger.warning(f"Auction failed (buyer insufficient funds): {listing_id}")
            return None

        # Transfer funds
        buyer.balance_bdt -= final_price
        seller.balance_bdt += final_price

        # Transfer land
        land.owner_id = buyer.user_id
        land.for_sale = False
        land.fenced = False
        land.passcode_hash = None

        # Create transaction
        transaction = Transaction(
            listing_id=listing_id,
            land_id=listing.land_id,
            buyer_id=buyer.user_id,
            seller_id=seller.user_id,
            amount_bdt=final_price,
            transaction_type=TransactionType.AUCTION,
            status=TransactionStatus.COMPLETED
        )

        db.add(transaction)

        # Mark listing as sold
        listing.status = ListingStatus.SOLD

        await db.commit()
        await db.refresh(transaction)

        # Invalidate caches
        await cache_service.delete(f"listing:{listing_id}")
        await cache_service.delete(f"land:{listing.land_id}")

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

        # Mark land as not for sale
        result = await db.execute(
            select(Land).where(Land.land_id == listing.land_id)
        )
        land = result.scalar_one_or_none()
        if land:
            land.for_sale = False

        await db.commit()
        await db.refresh(listing)

        await cache_service.delete(f"listing:{listing_id}")
        await cache_service.delete(f"land:{listing.land_id}")

        logger.info(f"Listing cancelled: {listing_id}")

        return listing


# Global instance
marketplace_service = MarketplaceService()
