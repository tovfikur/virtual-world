"""
Biome Trading Service
Handles buy/sell operations for biome shares
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Optional, List
import uuid
import logging

from app.models.biome_market import BiomeMarket
from app.models.biome_holding import BiomeHolding
from app.models.transaction import Transaction, TransactionType, TransactionStatus
from app.models.user import User
from app.models.land import Biome
from app.services.biome_market_service import biome_market_service

logger = logging.getLogger(__name__)

# Platform fee for biome trading (2%)
BIOME_TRADE_FEE_PERCENT = 2.0


class BiomeTradingService:
    """Service for biome share trading operations."""

    @staticmethod
    async def buy_shares(
        db: AsyncSession,
        user_id: uuid.UUID,
        biome: Biome,
        amount_bdt: int
    ) -> Transaction:
        """
        Buy biome shares with BDT.
        
        Args:
            db: Database session
            user_id: User ID
            biome: Biome type to buy
            amount_bdt: Amount in BDT to spend
            
        Returns:
            Transaction record
            
        Raises:
            ValueError: If validation fails
        """
        # Get user
        result = await db.execute(
            select(User).where(User.user_id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Check balance
        if user.balance_bdt < amount_bdt:
            raise ValueError(f"Insufficient balance: {user.balance_bdt} < {amount_bdt}")

        # Validate transaction size against market safeguards
        validation = await biome_market_service.validate_transaction_size(db, biome, amount_bdt)
        if not validation["valid"]:
            raise ValueError(f"Transaction size exceeds limit: {validation['warnings'][0]}")

        # Get market
        market = await biome_market_service.get_market(db, biome)

        # Calculate shares to buy
        shares = amount_bdt / market.share_price_bdt

        # Calculate platform fee (2%)
        platform_fee = int(amount_bdt * (BIOME_TRADE_FEE_PERCENT / 100))
        total_deduction = amount_bdt + platform_fee

        # Check balance including fee
        if user.balance_bdt < total_deduction:
            raise ValueError(f"Insufficient balance for purchase and fees: {user.balance_bdt} < {total_deduction}")

        # Get or create holding
        result = await db.execute(
            select(BiomeHolding).where(
                BiomeHolding.user_id == user_id,
                BiomeHolding.biome == biome
            ).with_for_update()
        )
        holding = result.scalar_one_or_none()

        if not holding:
            holding = BiomeHolding(
                user_id=user_id,
                biome=biome,
                shares=0.0,
                average_buy_price_bdt=0.0,
                total_invested_bdt=0
            )
            db.add(holding)

        # Update user balance (deduct shares + fee)
        user.balance_bdt -= total_deduction

        # Update holding
        holding.add_shares(shares, market.share_price_bdt)

        # Create transaction record in unified table
        transaction = Transaction(
            buyer_id=user_id,
            seller_id=None,  # No seller in biome trading
            land_id=None,  # Not a land trade
            listing_id=None,
            transaction_type=TransactionType.BIOME_BUY,
            amount_bdt=amount_bdt,
            status=TransactionStatus.COMPLETED,
            platform_fee_bdt=platform_fee,  # Tracked fee
            gateway_fee_bdt=0,
            completed_at=datetime.utcnow(),
            # Biome trading specific fields
            biome=biome.value,
            shares=shares,
            price_per_share_bdt=market.share_price_bdt
        )
        db.add(transaction)

        await db.commit()
        await db.refresh(transaction)

        logger.info(
            f"Buy executed: user={user_id}, biome={biome.value}, "
            f"shares={shares:.4f}, price={market.share_price_bdt}, fee={platform_fee}"
        )

        return transaction

    @staticmethod
    async def sell_shares(
        db: AsyncSession,
        user_id: uuid.UUID,
        biome: Biome,
        shares: float
    ) -> Transaction:
        """
        Sell biome shares for BDT.
        
        Args:
            db: Database session
            user_id: User ID
            biome: Biome type to sell
            shares: Number of shares to sell
            
        Returns:
            Transaction record
            
        Raises:
            ValueError: If validation fails
        """
        # Get holding
        result = await db.execute(
            select(BiomeHolding).where(
                BiomeHolding.user_id == user_id,
                BiomeHolding.biome == biome
            ).with_for_update()
        )
        holding = result.scalar_one_or_none()

        if not holding or holding.shares < shares:
            raise ValueError(f"Insufficient shares: {holding.shares if holding else 0} < {shares}")

        # Get market
        market = await biome_market_service.get_market(db, biome)

        # Calculate sale amount
        total_amount = int(shares * market.share_price_bdt)

        # Calculate platform fee on proceeds (2%)
        platform_fee = int(total_amount * (BIOME_TRADE_FEE_PERCENT / 100))
        net_proceeds = total_amount - platform_fee

        # Calculate realized gain
        avg_buy_price = holding.remove_shares(shares)
        realized_gain = int((market.share_price_bdt - avg_buy_price) * shares)

        # Get user
        result = await db.execute(
            select(User).where(User.user_id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Update user balance (add net proceeds after fee)
        user.balance_bdt += net_proceeds

        # Create transaction record in unified table
        transaction = Transaction(
            buyer_id=user_id,
            seller_id=None,  # No specific seller
            land_id=None,  # Not a land trade
            listing_id=None,
            transaction_type=TransactionType.BIOME_SELL,
            amount_bdt=total_amount,
            status=TransactionStatus.COMPLETED,
            platform_fee_bdt=platform_fee,  # Fee deducted from proceeds
            gateway_fee_bdt=0,
            completed_at=datetime.utcnow(),
            # Biome trading specific fields
            biome=biome.value,
            shares=shares,
            price_per_share_bdt=market.share_price_bdt
        )
        db.add(transaction)

        await db.commit()
        await db.refresh(transaction)

        logger.info(
            f"Sell executed: user={user_id}, biome={biome.value}, "
            f"shares={shares:.4f}, price={market.share_price_bdt}, gain={realized_gain}, fee={platform_fee}"
        )

        return transaction

    @staticmethod
    async def get_user_portfolio(
        db: AsyncSession,
        user_id: uuid.UUID
    ) -> dict:
        """
        Get user's biome portfolio with current values.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Dictionary with holdings and totals
        """
        # Get all holdings
        result = await db.execute(
            select(BiomeHolding).where(BiomeHolding.user_id == user_id)
        )
        holdings = result.scalars().all()

        # Get current market prices
        markets = await biome_market_service.get_all_markets(db)
        price_map = {market.biome: market.share_price_bdt for market in markets}

        # Calculate totals
        total_invested = 0
        total_current_value = 0.0
        holdings_data = []

        for holding in holdings:
            if holding.shares > 0:
                current_price = price_map.get(holding.biome, 0.0)
                holding_dict = holding.to_dict(current_price=current_price)
                holdings_data.append(holding_dict)
                
                total_invested += holding.total_invested_bdt
                total_current_value += holding.shares * current_price

        total_unrealized_gain = total_current_value - total_invested
        total_unrealized_gain_percent = (
            (total_unrealized_gain / total_invested * 100) if total_invested > 0 else 0.0
        )

        # Get user cash balance
        result = await db.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        cash_balance = user.balance_bdt if user else 0

        return {
            "holdings": holdings_data,
            "total_invested_bdt": total_invested,
            "total_current_value_bdt": total_current_value,
            "total_unrealized_gain_bdt": total_unrealized_gain,
            "total_unrealized_gain_percent": total_unrealized_gain_percent,
            "cash_balance_bdt": cash_balance
        }

    @staticmethod
    async def get_transaction_history(
        db: AsyncSession,
        user_id: uuid.UUID,
        biome: Optional[Biome] = None,
        page: int = 1,
        limit: int = 50
    ) -> dict:
        """
        Get user's transaction history.
        
        Args:
            db: Database session
            user_id: User ID
            biome: Optional biome filter
            page: Page number
            limit: Items per page
            
        Returns:
            Dictionary with transactions and pagination
        """
        query = select(BiomeTransaction).where(
            BiomeTransaction.user_id == user_id
        )

        if biome:
            query = query.where(BiomeTransaction.biome == biome)

        # Get total count
        count_result = await db.execute(
            select(func.count(BiomeTransaction.transaction_id)).select_from(
                BiomeTransaction
            ).where(BiomeTransaction.user_id == user_id)
        )
        total = count_result.scalar()

        # Apply pagination
        offset = (page - 1) * limit
        query = query.order_by(BiomeTransaction.executed_at.desc())
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        transactions = result.scalars().all()

        return {
            "transactions": [txn.to_dict() for txn in transactions],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if total > 0 else 0,
                "has_next": page * limit < total,
                "has_prev": page > 1
            }
        }


# Global instance
biome_trading_service = BiomeTradingService()
