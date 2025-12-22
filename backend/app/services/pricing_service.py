"""
Pricing engine for aggregating LP quotes and computing spreads/markups.
Handles FX/CFD pricing with tick normalization and feed publishing.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models.instrument import Instrument
from app.models.price_history import QuoteLevel, PriceHistory, TimeframeEnum, CorporateAction
from app.db.session import get_db

logger = logging.getLogger(__name__)


class PricingConfig:
    """Configuration for pricing behavior per instrument/asset class."""
    
    def __init__(self, 
                 base_spread_bp: float = 2.0,  # 2 basis points default
                 fx_spread_bp: float = 1.0,    # FX typically 1bp
                 cfd_spread_bp: float = 3.0,   # CFDs wider 3bp
                 cfd_markup_bp: float = 1.0,   # CFD markup
                 stale_quote_timeout_sec: int = 30,
                 tick_normalization: bool = True):
        """
        Args:
            base_spread_bp: Base spread in basis points
            fx_spread_bp: FX-specific spread
            cfd_spread_bp: CFD spread
            cfd_markup_bp: CFD broker markup
            stale_quote_timeout_sec: Consider quotes stale after N seconds
            tick_normalization: Whether to normalize to instrument tick size
        """
        self.base_spread_bp = base_spread_bp
        self.fx_spread_bp = fx_spread_bp
        self.cfd_spread_bp = cfd_spread_bp
        self.cfd_markup_bp = cfd_markup_bp
        self.stale_quote_timeout_sec = stale_quote_timeout_sec
        self.tick_normalization = tick_normalization


class PricingEngine:
    """
    Aggregates liquidity provider quotes and computes market prices with spreads/markups.
    Supports FX/CFD pricing with tick normalization.
    """
    
    def __init__(self, config: Optional[PricingConfig] = None):
        self.config = config or PricingConfig()
        # In-memory quote cache: {instrument_id: {provider: QuoteData}}
        self._quote_cache: Dict[int, Dict[str, Dict]] = {}
        # Market data subscribers for publishing updates
        self._market_data_subscribers: List = []
        
    async def add_quote(self, 
                       instrument_id: int,
                       provider: str,
                       bid: float,
                       ask: float,
                       bid_size: float,
                       ask_size: float,
                       db: AsyncSession) -> Dict:
        """
        Add or update a liquidity provider quote.
        
        Args:
            instrument_id: Instrument ID
            provider: LP identifier (e.g., 'lp1', 'lp2')
            bid: Bid price
            ask: Ask price
            bid_size: Bid volume
            ask_size: Ask volume
            db: Database session
            
        Returns:
            Aggregated quote with spread and markups
        """
        if instrument_id not in self._quote_cache:
            self._quote_cache[instrument_id] = {}
        
        spread = ask - bid
        spread_bp = (spread / bid * 10000) if bid > 0 else 0.0
        mid = (bid + ask) / 2.0
        
        # Store in cache
        self._quote_cache[instrument_id][provider] = {
            'bid': bid,
            'ask': ask,
            'bid_size': bid_size,
            'ask_size': ask_size,
            'spread': spread,
            'spread_bp': spread_bp,
            'mid': mid,
            'timestamp': datetime.utcnow(),
        }
        
        # Persist to database
        quote_level = QuoteLevel(
            instrument_id=instrument_id,
            provider=provider,
            bid_price=bid,
            ask_price=ask,
            bid_size=bid_size,
            ask_size=ask_size,
            spread=spread,
            spread_bp=spread_bp,
            mid=mid,
        )
        db.add(quote_level)
        await db.flush()
        
        # Get aggregated quote and publish
        agg_quote = await self.get_aggregated_quote(instrument_id, db)
        await self._publish_quote_update(instrument_id, agg_quote)
        
        return agg_quote
    
    async def get_aggregated_quote(self, 
                                   instrument_id: int,
                                   db: AsyncSession) -> Dict:
        """
        Get aggregated quote from all active providers with spreads/markups applied.
        
        Returns:
            {
                'bid': float,
                'ask': float,
                'mid': float,
                'spread': float,
                'spread_bp': float,
                'bid_size': float,
                'ask_size': float,
                'num_providers': int,
                'best_bid': float,
                'best_ask': float,
            }
        """
        if instrument_id not in self._quote_cache or not self._quote_cache[instrument_id]:
            return None
        
        # Get instrument for type info
        stmt = select(Instrument).where(Instrument.id == instrument_id)
        result = await db.execute(stmt)
        instrument = result.scalars().first()
        if not instrument:
            return None
        
        quotes = self._quote_cache[instrument_id]
        now = datetime.utcnow()
        
        # Filter fresh quotes
        fresh_quotes = {
            provider: q for provider, q in quotes.items()
            if (now - q['timestamp']).total_seconds() < self.config.stale_quote_timeout_sec
        }
        
        if not fresh_quotes:
            return None
        
        # Best bid/ask (best bid = highest, best ask = lowest)
        bids = [q['bid'] for q in fresh_quotes.values()]
        asks = [q['ask'] for q in fresh_quotes.values()]
        
        best_bid = max(bids)
        best_ask = min(asks)
        mid = (best_bid + best_ask) / 2.0
        
        # Determine spread config based on asset class
        if instrument.asset_class == "FOREX":
            spread_bp = self.config.fx_spread_bp
        elif instrument.asset_class == "CFD":
            spread_bp = self.config.cfd_spread_bp
        else:
            spread_bp = self.config.base_spread_bp
        
        # Apply broker spread/markup
        adjusted_bid = best_bid - (best_bid * spread_bp / 10000)  # Lower bid
        adjusted_ask = best_ask + (best_ask * spread_bp / 10000)  # Raise ask
        
        # For CFDs, add markup
        if instrument.asset_class == "CFD":
            markup = best_bid * self.config.cfd_markup_bp / 10000
            adjusted_ask += markup
        
        # Normalize to tick size if enabled
        if self.config.tick_normalization and instrument.tick_size:
            adjusted_bid = self._normalize_to_tick(adjusted_bid, instrument.tick_size, round_down=True)
            adjusted_ask = self._normalize_to_tick(adjusted_ask, instrument.tick_size, round_down=False)
        
        spread = adjusted_ask - adjusted_bid
        spread_bp_result = (spread / adjusted_bid * 10000) if adjusted_bid > 0 else 0.0
        
        # Get total available liquidity
        total_bid_size = sum(q['bid_size'] for q in fresh_quotes.values())
        total_ask_size = sum(q['ask_size'] for q in fresh_quotes.values())
        
        return {
            'bid': adjusted_bid,
            'ask': adjusted_ask,
            'mid': (adjusted_bid + adjusted_ask) / 2.0,
            'spread': spread,
            'spread_bp': spread_bp_result,
            'bid_size': total_bid_size,
            'ask_size': total_ask_size,
            'best_bid': best_bid,
            'best_ask': best_ask,
            'num_providers': len(fresh_quotes),
            'timestamp': datetime.utcnow(),
        }
    
    def _normalize_to_tick(self, price: float, tick_size: float, round_down: bool = True) -> float:
        """Normalize price to instrument tick size."""
        if tick_size <= 0:
            return price
        
        ticks = price / tick_size
        if round_down:
            ticks = int(ticks)  # Floor
        else:
            ticks = int(ticks) + (1 if ticks % 1 > 0 else 0)  # Ceil
        
        return ticks * tick_size
    
    async def get_top_of_book(self, instrument_id: int, db: AsyncSession) -> Dict:
        """Get Level 1 market data (top of book)."""
        return await self.get_aggregated_quote(instrument_id, db)
    
    async def get_depth(self, instrument_id: int, levels: int = 5, db: AsyncSession = None) -> List[Dict]:
        """
        Get Level 2 depth (order book snapshot).
        In real implementation, this would pull from order book.
        For now, returns simplified depth from quote levels.
        """
        if instrument_id not in self._quote_cache:
            return []
        
        quotes = self._quote_cache[instrument_id]
        depth = []
        
        # Bid side (descending)
        bids = sorted([
            {'price': q['bid'], 'size': q['bid_size'], 'provider': p}
            for p, q in quotes.items()
        ], key=lambda x: x['price'], reverse=True)[:levels]
        
        # Ask side (ascending)
        asks = sorted([
            {'price': q['ask'], 'size': q['ask_size'], 'provider': p}
            for p, q in quotes.items()
        ], key=lambda x: x['price'])[:levels]
        
        return {'bids': bids, 'asks': asks}
    
    async def apply_corporate_action(self,
                                     instrument_id: int,
                                     action: CorporateAction,
                                     db: AsyncSession) -> None:
        """
        Apply corporate action (split, dividend) to price history.
        Updates adjustment factor on PriceHistory records.
        """
        if action.action_type == "SPLIT" and action.ratio:
            # For splits, adjustment factor = ratio (e.g., 2.0 for 2:1 split)
            # Older prices adjusted down: old_price / ratio
            stmt = select(PriceHistory).where(
                (PriceHistory.instrument_id == instrument_id) &
                (PriceHistory.timestamp < action.effective_date)
            )
            result = await db.execute(stmt)
            for price_record in result.scalars():
                price_record.adjustment_factor *= action.ratio
        
        elif action.action_type == "REVERSE_SPLIT" and action.ratio:
            # For reverse splits, adjustment = 1/ratio
            stmt = select(PriceHistory).where(
                (PriceHistory.instrument_id == instrument_id) &
                (PriceHistory.timestamp < action.effective_date)
            )
            result = await db.execute(stmt)
            for price_record in result.scalars():
                price_record.adjustment_factor *= (1.0 / action.ratio)
        
        await db.commit()
        logger.info(f"Applied {action.action_type} to instrument {instrument_id}")
    
    async def _publish_quote_update(self, instrument_id: int, quote: Dict) -> None:
        """Publish quote update to all subscribers (for WebSocket feeds)."""
        for subscriber in self._market_data_subscribers:
            try:
                await subscriber(
                    event='quote_update',
                    instrument_id=instrument_id,
                    data=quote
                )
            except Exception as e:
                logger.error(f"Error publishing quote update: {e}")
    
    def subscribe(self, callback) -> None:
        """Subscribe to market data updates."""
        self._market_data_subscribers.append(callback)
    
    def unsubscribe(self, callback) -> None:
        """Unsubscribe from market data updates."""
        if callback in self._market_data_subscribers:
            self._market_data_subscribers.remove(callback)


# Global pricing engine instance
_pricing_engine: Optional[PricingEngine] = None


def get_pricing_engine() -> PricingEngine:
    """Get or create global pricing engine."""
    global _pricing_engine
    if _pricing_engine is None:
        _pricing_engine = PricingEngine()
    return _pricing_engine
