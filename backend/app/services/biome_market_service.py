"""
Biome Market Service
Handles market cash redistribution and price calculations
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from typing import Dict, List
import logging

from app.models.land import Land

from app.models.biome_market import BiomeMarket
from app.models.biome_price_history import BiomePriceHistory
from app.models.attention_score import AttentionScore
from app.models.land import Biome
from app.models.admin_config import AdminConfig
from app.services.attention_tracking_service import attention_tracking_service

logger = logging.getLogger(__name__)


class BiomeMarketService:
    """Service for biome market operations and redistribution."""

    @staticmethod
    async def initialize_markets(db: AsyncSession) -> List[BiomeMarket]:
        """
        Initialize biome markets if they don't exist.
        
        Args:
            db: Database session
            
        Returns:
            List of BiomeMarket records
        """
        markets = []
        
        for biome in Biome:
            result = await db.execute(
                select(BiomeMarket).where(BiomeMarket.biome == biome)
            )
            market = result.scalar_one_or_none()

            if not market:
                market = BiomeMarket(
                    biome=biome,
                    market_cash_bdt=1000000,  # Starting cash per biome
                    attention_score=0.0,
                    share_price_bdt=100.0,  # Starting price per share
                    total_shares=10000  # Starting shares
                )
                db.add(market)
                markets.append(market)
                logger.info(f"Initialized market for biome: {biome.value}")

        if markets:
            await db.commit()
            for market in markets:
                await db.refresh(market)

        # Get all markets
        result = await db.execute(select(BiomeMarket))
        return result.scalars().all()

    @staticmethod
    async def get_all_markets(db: AsyncSession) -> List[BiomeMarket]:
        """
        Get all biome markets.
        
        Args:
            db: Database session
            
        Returns:
            List of BiomeMarket records
        """
        result = await db.execute(select(BiomeMarket))
        return result.scalars().all()

    @staticmethod
    async def get_market(db: AsyncSession, biome: Biome) -> BiomeMarket:
        """
        Get market for specific biome.
        
        Args:
            db: Database session
            biome: Biome type
            
        Returns:
            BiomeMarket record
            
        Raises:
            ValueError: If market not found
        """
        result = await db.execute(
            select(BiomeMarket).where(BiomeMarket.biome == biome)
        )
        market = result.scalar_one_or_none()

        if not market:
            raise ValueError(f"Market not found for biome: {biome.value}")

        return market

    @staticmethod
    async def execute_redistribution(db: AsyncSession) -> Dict:
        """
        Execute attention-based market cash redistribution.
        
        Algorithm:
        1. Calculate Pool = TMC / 4 (25% of total market cash)
        2. Sum all attention scores: SumA
        3. Redistribute to each biome: R_i = Pool * (A_i / SumA)
        4. Update market cash: MC_i_new = MC_i + R_i
        5. Recalculate share prices
        6. Reset attention scores
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with redistribution results
        """
        # Get all markets
        markets = await BiomeMarketService.get_all_markets(db)

        if not markets:
            logger.warning("No markets found for redistribution")
            return {"redistributed": False, "reason": "no_markets"}

        # Get admin config for redistribution settings
        config_result = await db.execute(select(AdminConfig))
        config = config_result.scalar_one()

        # Check if prices are frozen
        if config.biome_prices_frozen:
            logger.info("Biome prices are frozen, skipping redistribution")
            return {"redistributed": False, "reason": "prices_frozen"}

        # Calculate total market cash (TMC)
        total_market_cash = sum(market.market_cash_bdt for market in markets)

        # Calculate redistribution pool using config percentage
        pool = int(total_market_cash * (config.redistribution_pool_percent / 100))

        logger.info(f"Starting redistribution - TMC: {total_market_cash}, Pool: {pool} ({config.redistribution_pool_percent}%)")

        # Get total attention per biome
        biome_attention = {}
        total_attention = 0.0

        for market in markets:
            attention = await attention_tracking_service.get_biome_total_attention(
                db, market.biome
            )
            biome_attention[market.biome] = attention
            total_attention += attention

        # If no attention, skip redistribution
        if total_attention == 0:
            logger.info("No attention recorded, skipping redistribution")
            return {"redistributed": False, "reason": "no_attention"}

        # Redistribute cash proportionally
        redistributions = {}

        for market in markets:
            attention = biome_attention[market.biome]
            
            # Calculate redistribution for this biome
            if attention > 0:
                redistribution_amount = int(pool * (attention / total_attention))
            else:
                redistribution_amount = 0

            # Update market cash
            old_cash = market.market_cash_bdt
            market.market_cash_bdt += redistribution_amount

            # Recalculate share price
            market.share_price_bdt = market.calculate_share_price()

            # Update redistribution timestamp
            market.last_redistribution = datetime.utcnow()

            # Store redistribution info
            redistributions[market.biome.value] = {
                "attention_score": attention,
                "redistribution_amount": redistribution_amount,
                "old_market_cash": old_cash,
                "new_market_cash": market.market_cash_bdt,
                "new_share_price": market.share_price_bdt
            }

            # Record price history
            price_history = BiomePriceHistory(
                biome=market.biome,
                price_bdt=market.share_price_bdt,
                market_cash_bdt=market.market_cash_bdt,
                attention_score=attention,
                timestamp=datetime.utcnow()
            )
            db.add(price_history)

            logger.info(
                f"Redistributed to {market.biome.value}: "
                f"{redistribution_amount} BDT (attention: {attention})"
            )

        await db.commit()

        # Reset attention scores
        await attention_tracking_service.reset_all_attention(db)

        logger.info("Redistribution complete")

        return {
            "redistributed": True,
            "total_market_cash": total_market_cash,
            "pool": pool,
            "total_attention": total_attention,
            "redistributions": redistributions,
            "markets": [m.to_dict() for m in markets],
            "timestamp": datetime.utcnow().isoformat()
        }

    @staticmethod
    async def get_price_history(
        db: AsyncSession,
        biome: Biome,
        hours: int = 24
    ) -> List[BiomePriceHistory]:
        """
        Get price history for a biome.
        
        Args:
            db: Database session
            biome: Biome type
            hours: Number of hours to look back
            
        Returns:
            List of BiomePriceHistory records
        """
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        result = await db.execute(
            select(BiomePriceHistory).where(
                BiomePriceHistory.biome == biome,
                BiomePriceHistory.timestamp >= cutoff_time
            ).order_by(BiomePriceHistory.timestamp.asc())
        )

        return result.scalars().all()

    @staticmethod
    async def validate_transaction_size(
        db: AsyncSession,
        biome: Biome,
        amount_bdt: int
    ) -> dict:
        """
        Validate that transaction size doesn't exceed safeguards.
        
        Args:
            db: Database session
            biome: Biome type
            amount_bdt: Transaction amount in BDT
            
        Returns:
            Dict with validation result and warnings
        """
        # Get admin config for transaction limits
        config_result = await db.execute(select(AdminConfig))
        config = config_result.scalar_one()

        market = await BiomeMarketService.get_market(db, biome)
        market_cap = market.market_cash_bdt
        max_transaction = int(market_cap * (config.max_transaction_percent / 100))
        
        result = {
            "valid": True,
            "warnings": [],
            "amount_bdt": amount_bdt,
            "market_cap": market_cap,
            "max_allowed": max_transaction,
            "percent_of_market": (amount_bdt / market_cap * 100) if market_cap > 0 else 0
        }
        
        if amount_bdt > max_transaction:
            result["valid"] = False
            result["warnings"].append(
                f"Transaction size ({amount_bdt} BDT) exceeds 10% market cap limit ({max_transaction} BDT)"
            )
            logger.warning(
                f"Transaction rejected for {biome.value}: {amount_bdt} BDT exceeds limit {max_transaction} BDT"
            )
        elif result["percent_of_market"] > 5:
            result["warnings"].append(
                f"Large transaction: {result['percent_of_market']:.2f}% of market cap"
            )
            logger.info(
                f"Large transaction detected for {biome.value}: "
                f"{result['percent_of_market']:.2f}% of market cap"
            )
        
        return result

    @staticmethod
    async def validate_price_movement(
        db: AsyncSession,
        biome: Biome,
        new_price: float,
        old_price: float
    ) -> dict:
        """
        Validate that price movement doesn't exceed safeguards.
        
        Args:
            db: Database session
            biome: Biome type
            new_price: New share price
            old_price: Previous share price
            
        Returns:
            Dict with validation result and warnings
        """
        # Get admin config for price movement limits
        config_result = await db.execute(select(AdminConfig))
        config = config_result.scalar_one()

        price_change_ratio = (new_price - old_price) / old_price if old_price > 0 else 0
        price_change_percent = abs(price_change_ratio) * 100
        max_move_percent = config.max_price_move_percent
        
        result = {
            "valid": True,
            "warnings": [],
            "old_price": old_price,
            "new_price": new_price,
            "change_percent": price_change_percent,
            "max_allowed_percent": max_move_percent,
            "direction": "up" if price_change_ratio > 0 else "down"
        }
        
        if price_change_percent > max_move_percent:
            result["valid"] = False
            result["warnings"].append(
                f"Price movement ({price_change_percent:.2f}%) exceeds {max_move_percent}% per-cycle limit"
            )
            logger.warning(
                f"Excessive price movement for {biome.value}: "
                f"{price_change_percent:.2f}% (limit: {max_move_percent}%)"
            )
        elif price_change_percent > 2:
            result["warnings"].append(
                f"Significant price movement: {price_change_percent:.2f}%"
            )
            logger.info(
                f"Significant price movement for {biome.value}: {price_change_percent:.2f}%"
            )
        
        return result

    @staticmethod
    async def get_lands_by_biome(
        db: AsyncSession,
        biome: Biome
    ) -> List[Land]:
        """
        Get all lands that have a specific biome.
        
        Args:
            db: Database session
            biome: Biome type to filter by
            
        Returns:
            List of Land records with that biome
        """
        result = await db.execute(
            select(Land).where(Land.biome == biome)
        )
        return result.scalars().all()

    @staticmethod
    async def get_land_owners_affected_by_biome(
        db: AsyncSession,
        biome: Biome
    ) -> Dict:
        """
        Get analysis of land owners affected by biome price changes.
        
        Shows which users own lands with a specific biome and how many.
        Useful for understanding who benefits from biome trading activity.
        
        Args:
            db: Database session
            biome: Biome type
            
        Returns:
            Dict with owner IDs and their land counts in that biome
        """
        lands = await BiomeMarketService.get_lands_by_biome(db, biome)
        
        owner_analysis = {}
        for land in lands:
            owner_id = str(land.owner_id) if land.owner_id else None
            if owner_id:
                if owner_id not in owner_analysis:
                    owner_analysis[owner_id] = {
                        "land_count": 0,
                        "lands": []
                    }
                owner_analysis[owner_id]["land_count"] += 1
                owner_analysis[owner_id]["lands"].append({
                    "land_id": str(land.land_id),
                    "biome": land.biome.value
                })
        
        return {
            "biome": biome.value,
            "total_lands_with_biome": len(lands),
            "affected_owners": len(owner_analysis),
            "owner_analysis": owner_analysis
        }


# Global instance
biome_market_service = BiomeMarketService()
