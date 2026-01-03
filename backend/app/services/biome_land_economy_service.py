"""
Biome Land Economy Service
Handles global land price adjustments across all biomes based on buy/sell events
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Dict, List
import logging

from app.models.biome_land_market import BiomeLandMarket
from app.models.land import Biome, Land
from app.models.transaction import Transaction, TransactionType

logger = logging.getLogger(__name__)


class BiomeLandEconomyService:
    """Service for global land market economy management."""

    # Number of biome types
    TOTAL_BIOMES = 7  # ocean, beach, plains, forest, desert, mountain, snow

    @staticmethod
    async def initialize_markets(db: AsyncSession) -> List[BiomeLandMarket]:
        """
        Initialize biome land markets if they don't exist.
        
        Args:
            db: Database session
            
        Returns:
            List of BiomeLandMarket records
        """
        markets = []
        
        for biome in Biome:
            result = await db.execute(
                select(BiomeLandMarket).where(BiomeLandMarket.biome == biome)
            )
            market = result.scalar_one_or_none()

            if not market:
                market = BiomeLandMarket(
                    biome=biome,
                    sold_lands_count=0,
                    average_price_bdt=0.0,
                    total_market_value_bdt=0,
                )
                db.add(market)
                markets.append(market)
        
        if markets:
            await db.commit()
        
        return markets

    @staticmethod
    async def handle_land_purchase(
        db: AsyncSession,
        land_id: str,
        amount_paid_bdt: int,
        buyer_id: str,
        seller_id: str
    ) -> Dict:
        """
        Handle land purchase and apply global biome economy adjustments.
        
        When land is purchased:
        1. Divide payment equally across all biomes
        2. Distribute each biome's share to all sold lands in that biome
        3. Increase prices proportionally
        
        Formula:
            ΔPrice_i = amount_paid_bdt / (TOTAL_BIOMES × SoldLandsCount_i)
        
        Args:
            db: Database session
            land_id: UUID of land being purchased
            amount_paid_bdt: Amount paid for the land
            buyer_id: UUID of buyer
            seller_id: UUID of seller
            
        Returns:
            Dict with market impact details
        """
        logger.info(f"🌍 ECONOMY SERVICE CALLED: land_id={land_id}, amount={amount_paid_bdt} BDT")
        logger.info(f"📊 BUY EVENT: C = {amount_paid_bdt} BDT, X = {BiomeLandEconomyService.TOTAL_BIOMES} biomes")
        try:
            # Fetch land details
            land_result = await db.execute(select(Land).where(Land.land_id == land_id))
            land = land_result.scalar_one_or_none()
            if not land:
                logger.error(f"Land not found: {land_id}")
                return {"error": "Land not found"}

            # Fetch all biome markets
            biome_markets_result = await db.execute(select(BiomeLandMarket))
            biome_markets = biome_markets_result.scalars().all()
            
            if not biome_markets:
                logger.warning("No biome markets initialized")
                return {"error": "Biome markets not initialized"}

            # Calculate per-biome share: PerBiomeShare = C / X
            per_biome_share = amount_paid_bdt / BiomeLandEconomyService.TOTAL_BIOMES
            logger.info(f"💰 PerBiomeShare = {amount_paid_bdt} / {BiomeLandEconomyService.TOTAL_BIOMES} = {per_biome_share:.2f} BDT per biome")

            # Track price changes
            price_changes = {}

            # For each biome, distribute its share
            for market in biome_markets:
                # Count actual owned lands in this biome from Land table
                lands_in_biome = await db.execute(
                    select(Land).where(
                        Land.biome == market.biome,
                        Land.owner_id.isnot(None)  # Only owned/sold lands
                    )
                )
                biome_lands = lands_in_biome.scalars().all()
                owned_lands_count = len(biome_lands)

                if owned_lands_count == 0:
                    # Skip biomes with no sold lands (avoid division by zero)
                    logger.info(f"⏭️  Biome {market.biome.value}: Xi = 0 (no sold lands), skipping")
                    continue

                # Calculate price increase for each land in this biome
                # Formula: ΔPi = PerBiomeShare / Xi = C / (X × Xi)
                price_increase = per_biome_share / owned_lands_count
                logger.info(f"📈 Biome {market.biome.value}: Xi = {owned_lands_count} lands, ΔPi = {per_biome_share:.2f} / {owned_lands_count} = {price_increase:.2f} BDT")

                if biome_lands:
                    for land_record in biome_lands:
                        old_price = land_record.price_base_bdt or 0
                        land_record.price_base_bdt = old_price + price_increase
                        
                        if market.biome.value not in price_changes:
                            price_changes[market.biome.value] = {
                                "old_price": old_price,
                                "increase": price_increase,
                                "new_price": land_record.price_base_bdt,
                                "affected_lands": len(biome_lands)
                            }

                # Update market stats
                market.total_market_value_bdt += int(per_biome_share)
                market.average_price_bdt = sum(land.price_base_bdt for land in biome_lands) / len(biome_lands) if biome_lands else 0
                market.last_transaction_at = datetime.utcnow()

            # DO NOT commit here - let caller handle commit
            # All changes are tracked in the session

            # Verify total redistribution (Economic Law: no leakage)
            total_redistributed = sum(
                pc["increase"] * pc["affected_lands"] 
                for pc in price_changes.values()
            )
            logger.info(
                f"✅ Land purchase processed: {land_id}, "
                f"Amount: {amount_paid_bdt} BDT, "
                f"Biomes affected: {len(price_changes)}, "
                f"Total redistributed: {total_redistributed:.2f} BDT (Expected: {amount_paid_bdt})"
            )
            logger.info(f"📋 Price changes: {price_changes}")

            return {
                "success": True,
                "amount_paid_bdt": amount_paid_bdt,
                "per_biome_share": per_biome_share,
                "price_changes": price_changes,
                "total_redistributed": total_redistributed,
                "message": f"Land prices updated in {len(price_changes)} biomes"
            }

        except Exception as e:
            logger.error(f"Error processing land purchase: {e}")
            await db.rollback()
            return {"error": str(e)}

    @staticmethod
    async def handle_land_sale(
        db: AsyncSession,
        land_id: str,
        amount_received_bdt: int,
        seller_id: str
    ) -> Dict:
        """
        Handle land sale and apply reverse biome economy adjustments.
        
        When land is sold:
        1. Divide sale proceeds equally across all biomes
        2. Distribute each biome's share across all sold lands in that biome
        3. Decrease prices proportionally (reverse of purchase)
        
        Formula:
            ΔPrice_i = -amount_received_bdt / (TOTAL_BIOMES × SoldLandsCount_i)
        
        Args:
            db: Database session
            land_id: UUID of land being sold
            amount_received_bdt: Amount received from the sale
            seller_id: UUID of seller
            
        Returns:
            Dict with market impact details
        """
        logger.info(f"💸 SELL EVENT: land_id={land_id}, amount={amount_received_bdt} BDT")
        logger.info(f"📊 SELL EVENT: C = {amount_received_bdt} BDT, X = {BiomeLandEconomyService.TOTAL_BIOMES} biomes")
        try:
            # Fetch land details
            land_result = await db.execute(select(Land).where(Land.land_id == land_id))
            land = land_result.scalar_one_or_none()
            if not land:
                logger.error(f"Land not found: {land_id}")
                return {"error": "Land not found"}

            # Fetch all biome markets
            biome_markets_result = await db.execute(select(BiomeLandMarket))
            biome_markets = biome_markets_result.scalars().all()
            
            if not biome_markets:
                logger.warning("No biome markets initialized")
                return {"error": "Biome markets not initialized"}

            # Calculate per-biome share: PerBiomeShare = C / X
            per_biome_share = amount_received_bdt / BiomeLandEconomyService.TOTAL_BIOMES
            logger.info(f"💰 PerBiomeShare = {amount_received_bdt} / {BiomeLandEconomyService.TOTAL_BIOMES} = {per_biome_share:.2f} BDT per biome")

            # Track price changes
            price_changes = {}

            # For each biome, distribute its share (reverse: decrease prices)
            for market in biome_markets:
                # Count actual owned lands in this biome from Land table
                lands_in_biome = await db.execute(
                    select(Land).where(
                        Land.biome == market.biome,
                        Land.owner_id.isnot(None)  # Only owned/sold lands
                    )
                )
                biome_lands = lands_in_biome.scalars().all()
                owned_lands_count = len(biome_lands)

                if owned_lands_count == 0:
                    logger.info(f"⏭️  Biome {market.biome.value}: Xi = 0 (no sold lands), skipping")
                    continue

                # Calculate price decrease for each land in this biome
                # Formula: ΔPi = PerBiomeShare / Xi = C / (X × Xi)
                price_decrease = per_biome_share / owned_lands_count
                logger.info(f"📉 Biome {market.biome.value}: Xi = {owned_lands_count} lands, ΔPi = {per_biome_share:.2f} / {owned_lands_count} = {price_decrease:.2f} BDT")

                if biome_lands:
                    for land_record in biome_lands:
                        old_price = land_record.price_base_bdt or 0
                        # Ensure price doesn't go negative
                        land_record.price_base_bdt = max(0, old_price - price_decrease)
                        
                        if market.biome.value not in price_changes:
                            price_changes[market.biome.value] = {
                                "old_price": old_price,
                                "decrease": price_decrease,
                                "new_price": land_record.price_base_bdt,
                                "affected_lands": len(biome_lands)
                            }

                # Update market stats
                market.total_market_value_bdt = max(0, market.total_market_value_bdt - int(per_biome_share))
                market.average_price_bdt = sum(land.price_base_bdt for land in biome_lands) / len(biome_lands) if biome_lands else 0
                market.last_transaction_at = datetime.utcnow()

            # DO NOT commit here - let caller handle commit
            # All changes are tracked in the session

            # Verify total redistribution (Economic Law: no leakage)
            total_redistributed = sum(
                pc["decrease"] * pc["affected_lands"] 
                for pc in price_changes.values()
            )
            logger.info(
                f"✅ Land sale processed: {land_id}, "
                f"Amount: {amount_received_bdt} BDT, "
                f"Biomes affected: {len(price_changes)}, "
                f"Total redistributed: {total_redistributed:.2f} BDT (Expected: {amount_received_bdt})"
            )
            logger.info(f"📋 Price changes: {price_changes}")

            return {
                "success": True,
                "amount_received_bdt": amount_received_bdt,
                "per_biome_share": per_biome_share,
                "price_changes": price_changes,
                "message": f"Land prices updated in {len(price_changes)} biomes"
            }

        except Exception as e:
            logger.error(f"Error processing land sale: {e}")
            await db.rollback()
            return {"error": str(e)}

    @staticmethod
    async def get_biome_market_stats(db: AsyncSession, biome: Biome = None) -> Dict:
        """
        Get current market statistics for biome(s).
        
        Args:
            db: Database session
            biome: Optional specific biome, or None for all biomes
            
        Returns:
            Dict with market statistics
        """
        try:
            if biome:
                result = await db.execute(
                    select(BiomeLandMarket).where(BiomeLandMarket.biome == biome)
                )
                markets = [result.scalar_one_or_none()]
            else:
                result = await db.execute(select(BiomeLandMarket))
                markets = result.scalars().all()

            market_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "biomes": [m.to_dict() for m in markets if m],
                "total_biomes_tracked": len([m for m in markets if m])
            }

            return market_data

        except Exception as e:
            logger.error(f"Error fetching biome market stats: {e}")
            return {"error": str(e)}

    @staticmethod
    async def update_sold_lands_count(
        db: AsyncSession,
        biome: Biome,
        increment: int = 1
    ) -> None:
        """
        Update the count of sold lands in a biome.
        
        Args:
            db: Database session
            biome: Biome type
            increment: Number to add/subtract (positive for new sale, negative for unsold)
        """
        try:
            result = await db.execute(
                select(BiomeLandMarket).where(BiomeLandMarket.biome == biome)
            )
            market = result.scalar_one_or_none()

            if market:
                market.sold_lands_count = max(0, market.sold_lands_count + increment)
                market.average_price_bdt = market.calculate_average_price()
                await db.commit()
                logger.debug(f"Updated {biome.value} sold lands count: {market.sold_lands_count}")

        except Exception as e:
            logger.error(f"Error updating sold lands count: {e}")
            await db.rollback()
