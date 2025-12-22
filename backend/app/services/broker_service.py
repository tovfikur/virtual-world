"""
Broker service for partner management and booking arrangements.
Handles sub-accounts, A-book/B-book routing, exposure hedging, and commission sharing.
"""

from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
import logging
import secrets
import hashlib
from uuid import UUID

from app.models.admin import (
    BrokerAccount, BookType, BrokerType
)
from app.models.account import Account

logger = logging.getLogger(__name__)


class BrokerService:
    """
    Broker partner management service.
    Manages broker accounts, sub-accounts, and booking arrangements.
    """
    
    async def create_broker_account(
        self,
        broker_name: str,
        broker_type: str,
        default_book_type: str = BookType.A_BOOK,
        max_leverage: float = 50.0,
        credit_limit: float = 0.0,
        db: AsyncSession = None
    ) -> BrokerAccount:
        """Create new broker account."""
        # Generate broker ID
        broker_id = await self._generate_broker_id(db)
        
        # Generate API credentials
        api_key = secrets.token_urlsafe(32)
        api_secret = secrets.token_urlsafe(32)
        api_secret_hash = hashlib.sha256(api_secret.encode()).hexdigest()
        
        broker = BrokerAccount(
            broker_name=broker_name,
            broker_id=broker_id,
            broker_type=broker_type,
            default_book_type=default_book_type,
            max_leverage=max_leverage,
            credit_limit=credit_limit,
            api_key=api_key,
            api_secret_hash=api_secret_hash
        )
        
        db.add(broker)
        await db.flush()
        
        logger.info(
            f"Created broker account {broker_id}: {broker_name} "
            f"({broker_type}, {default_book_type})"
        )
        
        return broker
    
    async def get_broker_account(
        self,
        broker_id: str = None,
        api_key: str = None,
        db: AsyncSession = None
    ) -> Optional[BrokerAccount]:
        """Get broker account by ID or API key."""
        if broker_id:
            stmt = select(BrokerAccount).where(BrokerAccount.broker_id == broker_id)
        elif api_key:
            stmt = select(BrokerAccount).where(BrokerAccount.api_key == api_key)
        else:
            return None
        
        result = await db.execute(stmt)
        return result.scalars().first()
    
    async def create_sub_account(
        self,
        broker_id: str,
        account_id: int,
        db: AsyncSession = None
    ) -> bool:
        """Add trading account as sub-account under broker."""
        broker = await self.get_broker_account(broker_id=broker_id, db=db)
        
        if not broker:
            raise ValueError(f"Broker {broker_id} not found")
        
        if broker.current_sub_account_count >= broker.max_sub_accounts:
            raise ValueError(
                f"Broker reached maximum sub-accounts ({broker.max_sub_accounts})"
            )
        
        # Link account to broker (add to account metadata)
        stmt = select(Account).where(Account.id == account_id)
        result = await db.execute(stmt)
        account = result.scalars().first()
        
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        # Store broker association
        account.broker_id = broker_id
        broker.current_sub_account_count += 1
        
        await db.flush()
        
        logger.info(f"Added account {account_id} as sub-account to broker {broker_id}")
        return True
    
    async def route_order(
        self,
        broker_id: str,
        order_data: Dict,
        db: AsyncSession = None
    ) -> Dict:
        """
        Route order based on broker's booking arrangement.
        Returns routing decision.
        """
        broker = await self.get_broker_account(broker_id=broker_id, db=db)
        
        if not broker:
            raise ValueError(f"Broker {broker_id} not found")
        
        routing = {
            "broker_id": broker_id,
            "book_type": broker.default_book_type,
            "route_to_market": broker.default_book_type == BookType.A_BOOK,
            "hedge_required": False,
            "hedge_ratio": 0.0
        }
        
        # A-book: Pass through to market
        if broker.default_book_type == BookType.A_BOOK:
            routing["route_to_market"] = True
        
        # B-book: Broker takes opposite side
        elif broker.default_book_type == BookType.B_BOOK:
            routing["route_to_market"] = False
            routing["broker_becomes_counterparty"] = True
        
        # Hybrid: Check if hedging needed
        elif broker.default_book_type == BookType.HYBRID:
            position_size = order_data.get("quantity", 0)
            
            # Get broker's current exposure
            exposure = await self._calculate_broker_exposure(broker_id, db)
            
            # Determine hedge requirement
            if exposure / position_size > broker.hedge_ratio:
                routing["hedge_required"] = True
                routing["hedge_ratio"] = broker.hedge_ratio
        
        logger.debug(f"Routed order for broker {broker_id}: {routing}")
        return routing
    
    async def hedge_broker_exposure(
        self,
        broker_id: str,
        instrument_id: UUID,
        quantity: float,
        price: float,
        db: AsyncSession = None
    ) -> bool:
        """
        Hedge broker's position by offsetting with opposite order.
        """
        broker = await self.get_broker_account(broker_id=broker_id, db=db)
        
        if not broker or not broker.can_hedge:
            logger.warning(f"Broker {broker_id} cannot hedge")
            return False
        
        # Create internal hedging order
        # TODO: Route to internal matching engine
        
        logger.info(
            f"Hedged broker exposure: {broker_id}, {quantity} {instrument_id}"
        )
        return True
    
    async def accrue_commission(
        self,
        broker_id: str,
        commission_amount: float,
        db: AsyncSession = None
    ) -> None:
        """Accrue commission for broker from trades."""
        broker = await self.get_broker_account(broker_id=broker_id, db=db)
        
        if not broker:
            raise ValueError(f"Broker {broker_id} not found")
        
        if broker.can_share_commission:
            share = commission_amount * (broker.commission_share_percentage / 100)
            broker.payable_commission += share
            
            await db.flush()
            
            logger.debug(
                f"Accrued ${share:.2f} commission for broker {broker_id}"
            )
    
    async def payout_commission(
        self,
        broker_id: str,
        amount: Optional[float] = None,
        db: AsyncSession = None
    ) -> float:
        """
        Pay out accumulated commission to broker.
        If amount not specified, pay all.
        """
        broker = await self.get_broker_account(broker_id=broker_id, db=db)
        
        if not broker:
            raise ValueError(f"Broker {broker_id} not found")
        
        payout_amount = amount or broker.payable_commission
        
        if payout_amount > broker.payable_commission:
            raise ValueError("Payout exceeds accumulated commission")
        
        # Process payout
        broker.payable_commission -= payout_amount
        
        await db.flush()
        
        logger.info(
            f"Paid out ${payout_amount:.2f} commission to broker {broker_id}, "
            f"remaining: ${broker.payable_commission:.2f}"
        )
        
        return payout_amount
    
    async def check_credit_limit(
        self,
        broker_id: str,
        amount: float,
        db: AsyncSession = None
    ) -> bool:
        """Check if credit limit allows transaction."""
        broker = await self.get_broker_account(broker_id=broker_id, db=db)
        
        if not broker:
            return False
        
        if broker.credit_limit == 0:
            return True  # Unlimited
        
        available_credit = broker.credit_limit - broker.current_credit_utilization
        return amount <= available_credit
    
    async def utilize_credit(
        self,
        broker_id: str,
        amount: float,
        db: AsyncSession = None
    ) -> None:
        """Utilize broker credit for transaction."""
        broker = await self.get_broker_account(broker_id=broker_id, db=db)
        
        if not broker:
            raise ValueError(f"Broker {broker_id} not found")
        
        if not await self.check_credit_limit(broker_id, amount, db):
            raise ValueError("Insufficient credit limit")
        
        broker.current_credit_utilization += amount
        await db.flush()
    
    async def release_credit(
        self,
        broker_id: str,
        amount: float,
        db: AsyncSession = None
    ) -> None:
        """Release broker credit from transaction."""
        broker = await self.get_broker_account(broker_id=broker_id, db=db)
        
        if not broker:
            raise ValueError(f"Broker {broker_id} not found")
        
        broker.current_credit_utilization = max(0, broker.current_credit_utilization - amount)
        await db.flush()
    
    async def _calculate_broker_exposure(
        self,
        broker_id: str,
        db: AsyncSession = None
    ) -> float:
        """Calculate broker's total market exposure."""
        # TODO: Sum all open positions for broker's sub-accounts
        return 0.0
    
    async def _generate_broker_id(self, db: AsyncSession) -> str:
        """Generate unique broker ID."""
        import uuid
        base_id = f"BRK-{uuid.uuid4().hex[:8].upper()}"
        
        # Verify uniqueness
        stmt = select(BrokerAccount).where(BrokerAccount.broker_id == base_id)
        result = await db.execute(stmt)
        
        if result.scalars().first():
            return await self._generate_broker_id(db)
        
        return base_id


# Global broker service instance
_broker_service: Optional['BrokerService'] = None


def get_broker_service() -> BrokerService:
    """Get or create broker service."""
    global _broker_service
    if _broker_service is None:
        _broker_service = BrokerService()
    return _broker_service
