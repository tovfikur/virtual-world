"""
Settlement and clearing service.
Handles trade confirmation, netting, T+N settlement, custody updates, and payout flows.
"""

from typing import List, Optional, Dict, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from datetime import datetime, timedelta
import logging
from uuid import UUID

from app.models.account import Account
from app.models.trade import Trade
from app.models.instrument import Instrument
from app.models.settlement import (
    TradeConfirmation, SettlementQueue, CustodyBalance, SettlementRecord,
    NetSettlementBatch, SettlementException, ReconciliationReport,
    SettlementStatus, SettlementType, CustodyType
)
from app.services.fee_service import get_fee_service
from app.services.margin_service import get_margin_service

logger = logging.getLogger(__name__)


class SettlementService:
    """
    Manages trade settlement pipeline.
    
    Flow:
    1. Trade Confirmation: Create confirmation record after order match
    2. Bilateral Confirmation: Both buyer and seller confirm
    3. Netting: Group trades for net settlement
    4. Settlement: Transfer cash/assets on settlement date
    5. Custody: Update custody balances
    6. Reconciliation: Validate custody accounts
    """
    
    def __init__(self):
        self.fee_service = get_fee_service()
        self.margin_service = get_margin_service()
    
    async def create_trade_confirmation(
        self,
        trade: Trade,
        settlement_days: int = 2,  # Default T+2
        db: AsyncSession = None
    ) -> TradeConfirmation:
        """
        Create trade confirmation after order match.
        
        Args:
            trade: Executed trade
            settlement_days: Days until settlement (T+N)
            db: Database session
            
        Returns:
            TradeConfirmation record
        """
        # Calculate settlement date
        settlement_date = datetime.utcnow() + timedelta(days=settlement_days)
        
        # Get accounts and instrument
        buyer = await self._get_account(trade.buyer_account_id, db)
        seller = await self._get_account(trade.seller_account_id, db)
        instrument = await self._get_instrument(trade.instrument_id, db)
        
        # Calculate amounts
        gross_amount = trade.quantity * trade.execution_price
        
        # Calculate fees (using fee service)
        buyer_fee = await self.fee_service.calculate_trade_fee(
            buyer, instrument, trade.quantity, trade.execution_price, "BUY", db
        )
        seller_fee = await self.fee_service.calculate_trade_fee(
            seller, instrument, trade.quantity, trade.execution_price, "SELL", db
        )
        
        net_amount = gross_amount - buyer_fee - seller_fee
        
        # Create confirmation
        confirmation = TradeConfirmation(
            trade_id=trade.id,
            buyer_account_id=trade.buyer_account_id,
            seller_account_id=trade.seller_account_id,
            instrument_id=trade.instrument_id,
            quantity=trade.quantity,
            price=trade.execution_price,
            gross_amount=gross_amount,
            buyer_fee=buyer_fee,
            seller_fee=seller_fee,
            net_amount=net_amount,
            settlement_type=self._determine_settlement_type(instrument),
            settlement_date=settlement_date,
            settlement_status=SettlementStatus.PENDING
        )
        
        db.add(confirmation)
        await db.flush()
        
        # Create settlement queue entry
        queue_entry = SettlementQueue(
            trade_confirmation_id=confirmation.id,
            status=SettlementStatus.PENDING,
            settlement_date=settlement_date
        )
        
        db.add(queue_entry)
        await db.flush()
        
        logger.info(
            f"Created trade confirmation {confirmation.id}: "
            f"BUY {trade.quantity} {instrument.symbol} @ {trade.execution_price}, "
            f"Settlement: {settlement_date.date()}"
        )
        
        return confirmation
    
    async def confirm_trade(
        self,
        confirmation_id: UUID,
        account_id: int,
        is_buyer: bool,
        db: AsyncSession = None
    ) -> TradeConfirmation:
        """
        Confirm trade from one party (buyer or seller).
        Once both confirm, settlement can proceed.
        """
        stmt = select(TradeConfirmation).where(TradeConfirmation.id == confirmation_id)
        result = await db.execute(stmt)
        confirmation = result.scalars().first()
        
        if not confirmation:
            raise ValueError(f"Confirmation {confirmation_id} not found")
        
        # Validate account matches
        if is_buyer and account_id != confirmation.buyer_account_id:
            raise ValueError("Not the buyer")
        elif not is_buyer and account_id != confirmation.seller_account_id:
            raise ValueError("Not the seller")
        
        # Mark as confirmed
        if is_buyer:
            confirmation.buyer_confirmed = True
            confirmation.buyer_confirmed_at = datetime.utcnow()
        else:
            confirmation.seller_confirmed = True
            confirmation.seller_confirmed_at = datetime.utcnow()
        
        # Check if both confirmed
        if confirmation.buyer_confirmed and confirmation.seller_confirmed:
            confirmation.settlement_status = SettlementStatus.CONFIRMED
            logger.info(
                f"Both parties confirmed trade {confirmation.trade_id}, "
                f"ready for settlement"
            )
        
        await db.flush()
        return confirmation
    
    async def net_trades(
        self,
        account_id: Optional[int] = None,
        instrument_id: Optional[UUID] = None,
        settlement_date: Optional[datetime] = None,
        db: AsyncSession = None
    ) -> NetSettlementBatch:
        """
        Create netting batch for multiple trades.
        Reduces settlement risk and operational burden.
        
        Netting combines:
        - Trades between same parties
        - Trades on same instrument
        - Same settlement date
        """
        # Build query for trades to net
        stmt = select(SettlementQueue).join(
            TradeConfirmation
        ).where(
            and_(
                SettlementQueue.status == SettlementStatus.CONFIRMED,
                SettlementQueue.is_netted == False
            )
        )
        
        if account_id:
            stmt = stmt.where(
                or_(
                    TradeConfirmation.buyer_account_id == account_id,
                    TradeConfirmation.seller_account_id == account_id
                )
            )
        
        if instrument_id:
            stmt = stmt.where(TradeConfirmation.instrument_id == instrument_id)
        
        if settlement_date:
            # Round to date only
            target_date = settlement_date.replace(hour=0, minute=0, second=0, microsecond=0)
            stmt = stmt.where(
                func.date(SettlementQueue.settlement_date) == target_date
            )
        
        result = await db.execute(stmt)
        queue_entries = result.scalars().all()
        
        if not queue_entries:
            logger.info("No trades to net")
            return None
        
        # Create batch
        batch = NetSettlementBatch(
            batch_number=self._generate_batch_number(),
            batch_date=datetime.utcnow(),
            settlement_date=queue_entries[0].settlement_date,
            account_id=account_id,
            instrument_id=instrument_id,
            status=SettlementStatus.NETTED
        )
        
        # Aggregate trades
        total_buy_qty = 0.0
        total_sell_qty = 0.0
        total_gross = 0.0
        total_fees = 0.0
        
        for queue_entry in queue_entries:
            confirmation = queue_entry.trade_confirmation_id  # This will be lazy-loaded
            
            # Track buy/sell quantities
            total_buy_qty += confirmation.quantity  # Simplified
            total_sell_qty += confirmation.quantity
            total_gross += confirmation.gross_amount
            total_fees += confirmation.buyer_fee + confirmation.seller_fee
            
            # Mark as netted
            queue_entry.is_netted = True
            queue_entry.netting_batch_id = batch.id
        
        # Calculate net settlement
        batch.trade_count = len(queue_entries)
        batch.gross_amount = total_gross
        batch.fees_collected = total_fees
        batch.net_amount = total_gross - total_fees
        batch.buy_quantity = total_buy_qty
        batch.sell_quantity = total_sell_qty
        batch.net_quantity = abs(total_buy_qty - total_sell_qty)
        
        db.add(batch)
        await db.flush()
        
        logger.info(
            f"Created netting batch {batch.batch_number}: "
            f"{len(queue_entries)} trades, net quantity: {batch.net_quantity}"
        )
        
        return batch
    
    async def settle_trade(
        self,
        confirmation_id: UUID,
        db: AsyncSession = None
    ) -> SettlementRecord:
        """
        Settle a single trade.
        Transfers cash/assets and updates custody balances.
        """
        stmt = select(TradeConfirmation).where(TradeConfirmation.id == confirmation_id)
        result = await db.execute(stmt)
        confirmation = result.scalars().first()
        
        if not confirmation:
            raise ValueError(f"Confirmation {confirmation_id} not found")
        
        if not (confirmation.buyer_confirmed and confirmation.seller_confirmed):
            raise ValueError("Trade not fully confirmed")
        
        try:
            # Get parties
            buyer = await self._get_account(confirmation.buyer_account_id, db)
            seller = await self._get_account(confirmation.seller_account_id, db)
            
            # Calculate payment flows
            buyer_pays = confirmation.gross_amount + confirmation.buyer_fee
            seller_receives = confirmation.gross_amount - confirmation.seller_fee
            
            # Update account balances
            buyer.balance -= buyer_pays
            seller.balance += seller_receives
            
            # Update custody balances
            await self._update_custody_balance(
                seller.id, confirmation.instrument_id,
                confirmation.quantity, "credit", db
            )
            await self._update_custody_balance(
                buyer.id, confirmation.instrument_id,
                confirmation.quantity, "debit", db
            )
            
            # Create settlement record
            settlement = SettlementRecord(
                trade_confirmation_id=confirmation.id,
                buyer_account_id=confirmation.buyer_account_id,
                seller_account_id=confirmation.seller_account_id,
                instrument_id=confirmation.instrument_id,
                quantity=confirmation.quantity,
                settlement_price=confirmation.price,
                settlement_amount=confirmation.gross_amount,
                buyer_pays=buyer_pays,
                seller_receives=seller_receives,
                platform_fee_collected=confirmation.buyer_fee + confirmation.seller_fee,
                settlement_type=confirmation.settlement_type,
                status=SettlementStatus.SETTLED,
                settlement_date=confirmation.settlement_date,
                actual_settlement_date=datetime.utcnow(),
                buyer_custody_updated=True,
                seller_custody_updated=True,
                buyer_custody_updated_at=datetime.utcnow(),
                seller_custody_updated_at=datetime.utcnow()
            )
            
            db.add(settlement)
            
            # Update confirmation
            confirmation.settlement_status = SettlementStatus.SETTLED
            confirmation.settled_at = datetime.utcnow()
            
            await db.flush()
            
            logger.info(
                f"Settled trade {confirmation.trade_id}: "
                f"Buyer paid ${buyer_pays:.2f}, Seller received ${seller_receives:.2f}"
            )
            
            return settlement
            
        except Exception as e:
            logger.error(f"Settlement failed for {confirmation_id}: {str(e)}")
            
            # Create exception record
            exception = SettlementException(
                trade_confirmation_id=confirmation.id,
                exception_type="settlement_failure",
                severity="high",
                description=str(e),
                affected_account_id=confirmation.buyer_account_id
            )
            db.add(exception)
            
            confirmation.settlement_status = SettlementStatus.FAILED
            confirmation.failure_reason = str(e)
            
            await db.flush()
            raise
    
    async def settle_batch(
        self,
        batch_id: UUID,
        db: AsyncSession = None
    ) -> Dict:
        """
        Settle all trades in a netting batch.
        """
        stmt = select(NetSettlementBatch).where(NetSettlementBatch.id == batch_id)
        result = await db.execute(stmt)
        batch = result.scalars().first()
        
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        # Get all queue entries in batch
        stmt = select(SettlementQueue).where(
            SettlementQueue.netting_batch_id == batch_id
        )
        result = await db.execute(stmt)
        queue_entries = result.scalars().all()
        
        settled_count = 0
        failed_count = 0
        settlement_records = []
        
        for queue_entry in queue_entries:
            try:
                settlement = await self.settle_trade(
                    queue_entry.trade_confirmation_id, db
                )
                settlement_records.append(settlement)
                settled_count += 1
                queue_entry.status = SettlementStatus.SETTLED
                queue_entry.processed_at = datetime.utcnow()
            except Exception as e:
                logger.warning(f"Failed to settle {queue_entry.trade_confirmation_id}: {str(e)}")
                failed_count += 1
        
        # Update batch
        batch.status = SettlementStatus.SETTLED
        batch.is_finalized = True
        batch.finalized_at = datetime.utcnow()
        
        await db.flush()
        
        logger.info(
            f"Settled batch {batch.batch_number}: "
            f"{settled_count} successful, {failed_count} failed"
        )
        
        return {
            "batch_id": batch_id,
            "settled_count": settled_count,
            "failed_count": failed_count,
            "total_amount": batch.net_amount,
            "settlement_records": settlement_records
        }
    
    async def _update_custody_balance(
        self,
        account_id: int,
        instrument_id: UUID,
        quantity: float,
        direction: str,  # "credit" or "debit"
        db: AsyncSession = None
    ) -> CustodyBalance:
        """Update custody balance for account/instrument."""
        stmt = select(CustodyBalance).where(
            and_(
                CustodyBalance.account_id == account_id,
                CustodyBalance.instrument_id == instrument_id
            )
        )
        result = await db.execute(stmt)
        custody = result.scalars().first()
        
        if not custody:
            # Create new custody balance
            custody = CustodyBalance(
                account_id=account_id,
                instrument_id=instrument_id,
                custody_type=CustodyType.SECURITIES,
                balance=0.0,
                quantity_settled=0.0
            )
            db.add(custody)
            await db.flush()
        
        # Update based on direction
        if direction == "credit":
            custody.quantity_settled += quantity
            custody.balance += quantity
        elif direction == "debit":
            custody.quantity_pending += quantity
        
        custody.updated_at = datetime.utcnow()
        
        return custody
    
    async def reconcile_custody(
        self,
        account_id: Optional[int] = None,
        custodian: Optional[str] = None,
        db: AsyncSession = None
    ) -> ReconciliationReport:
        """
        Reconcile custody balances against actual custodian records.
        """
        report = ReconciliationReport(
            report_date=datetime.utcnow(),
            period_start=datetime.utcnow() - timedelta(days=1),
            period_end=datetime.utcnow(),
            account_id=account_id,
            custodian=custodian,
            status="in_progress"
        )
        
        # Get custody balances
        stmt = select(CustodyBalance)
        if account_id:
            stmt = stmt.where(CustodyBalance.account_id == account_id)
        if custodian:
            stmt = stmt.where(CustodyBalance.custodian == custodian)
        
        result = await db.execute(stmt)
        custody_balances = result.scalars().all()
        
        # TODO: Fetch actual custodian balances
        # For now, assume internal records match custody
        
        total_expected = 0.0
        total_actual = 0.0
        matched = 0
        unmatched = 0
        
        for custody in custody_balances:
            expected = custody.balance
            actual = custody.balance  # In production: fetch from custodian
            total_expected += expected
            total_actual += actual
            
            if abs(expected - actual) < 0.01:
                matched += 1
            else:
                unmatched += 1
        
        report.expected_balance = total_expected
        report.actual_balance = total_actual
        report.difference = abs(total_expected - total_actual)
        report.is_balanced = report.difference < 0.01
        report.matched_trades = matched
        report.unmatched_trades = unmatched
        report.status = "complete"
        
        db.add(report)
        await db.flush()
        
        logger.info(
            f"Reconciliation complete: Expected=${total_expected:.2f}, "
            f"Actual=${total_actual:.2f}, Matched={matched}, Unmatched={unmatched}"
        )
        
        return report
    
    async def process_broker_payout(
        self,
        settlement_record_id: int,
        db: AsyncSession = None
    ) -> bool:
        """
        Process payout to broker partner.
        Updates settlement record with payout details.
        """
        stmt = select(SettlementRecord).where(SettlementRecord.id == settlement_record_id)
        result = await db.execute(stmt)
        settlement = result.scalars().first()
        
        if not settlement:
            raise ValueError(f"Settlement {settlement_record_id} not found")
        
        try:
            # TODO: Integrate with payment processor
            # For now, mark as paid
            
            settlement.broker_paid = True
            settlement.broker_paid_at = datetime.utcnow()
            settlement.broker_payment_reference = f"PAYOUT-{settlement.settlement_id}"
            
            await db.flush()
            
            logger.info(
                f"Processed broker payout for settlement {settlement.settlement_id}: "
                f"${settlement.seller_receives:.2f}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Broker payout failed: {str(e)}")
            return False
    
    def _determine_settlement_type(self, instrument: Instrument) -> str:
        """Determine settlement type based on instrument."""
        if instrument.asset_class in ["EQUITY", "BOND"]:
            return SettlementType.DVP  # Delivery vs Payment
        else:
            return SettlementType.CASH
    
    def _generate_batch_number(self) -> str:
        """Generate unique batch number."""
        import uuid
        return f"NET-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    
    async def _get_account(self, account_id: int, db: AsyncSession) -> Account:
        """Get account by ID."""
        stmt = select(Account).where(Account.id == account_id)
        result = await db.execute(stmt)
        return result.scalars().first()
    
    async def _get_instrument(self, instrument_id: UUID, db: AsyncSession) -> Instrument:
        """Get instrument by ID."""
        stmt = select(Instrument).where(Instrument.id == instrument_id)
        result = await db.execute(stmt)
        return result.scalars().first()


# Global settlement service instance
_settlement_service: Optional[SettlementService] = None


def get_settlement_service() -> SettlementService:
    """Get or create settlement service."""
    global _settlement_service
    if _settlement_service is None:
        _settlement_service = SettlementService()
    return _settlement_service
