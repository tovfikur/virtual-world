"""
Trade clearing and settlement models.
Handles trade confirmation, netting, T+N settlement, and custody balances.
"""

from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Boolean, Enum, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import enum
import uuid

from app.database import Base


class SettlementStatus(str, enum.Enum):
    """Settlement lifecycle statuses."""
    PENDING = "pending"           # Trade executed, awaiting confirmation
    CONFIRMED = "confirmed"       # Both sides confirmed
    NETTED = "netted"            # Included in netting pipeline
    SETTLED = "settled"          # Funds/assets transferred
    FAILED = "failed"            # Settlement failed
    REVERSED = "reversed"        # Settlement reversed


class SettlementType(str, enum.Enum):
    """Settlement types."""
    CASH = "cash"                # Cash settlement (FX, CFDs)
    PHYSICAL = "physical"        # Physical asset settlement (equities)
    NETTING = "netting"          # Net settlement
    DVP = "dvp"                 # Delivery vs Payment


class CustodyType(str, enum.Enum):
    """Custody balance types."""
    CASH = "cash"
    SECURITIES = "securities"
    CRYPTO = "crypto"


class TradeConfirmation(Base):
    """
    Trade confirmation record.
    Created immediately after order match.
    """
    __tablename__ = "trade_confirmations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Trade reference
    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False, unique=True)
    
    # Counterparties
    buyer_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    seller_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    
    # Trade details
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    gross_amount = Column(Float, nullable=False)  # quantity * price
    
    # Fees and adjustments
    buyer_fee = Column(Float, default=0.0)
    seller_fee = Column(Float, default=0.0)
    net_amount = Column(Float, nullable=False)  # gross - fees
    
    # Settlement details
    settlement_type = Column(String(50), default=SettlementType.CASH)
    settlement_date = Column(DateTime, nullable=False)  # T+N
    settlement_status = Column(String(50), default=SettlementStatus.PENDING)
    
    # Confirmation tracking
    buyer_confirmed = Column(Boolean, default=False)
    seller_confirmed = Column(Boolean, default=False)
    buyer_confirmed_at = Column(DateTime)
    seller_confirmed_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    settled_at = Column(DateTime)
    
    # Notes
    notes = Column(Text)
    failure_reason = Column(Text)
    
    __table_args__ = (
        UniqueConstraint('trade_id', name='uq_confirmation_trade_id'),
    )


class SettlementQueue(Base):
    """
    Settlement queue entry.
    Tracks trades waiting for settlement.
    """
    __tablename__ = "settlement_queue"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Trade reference
    trade_confirmation_id = Column(UUID(as_uuid=True), ForeignKey("trade_confirmations.id"), nullable=False)
    
    # Netting info
    netting_batch_id = Column(UUID(as_uuid=True))  # Belongs to a netting batch
    is_netted = Column(Boolean, default=False)
    
    # Queue status
    status = Column(String(50), default=SettlementStatus.PENDING)
    settlement_date = Column(DateTime, nullable=False)
    
    # Retry tracking
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime)
    max_retries = Column(Integer, default=3)
    
    # Timestamps
    queued_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    
    __table_args__ = (
        UniqueConstraint('trade_confirmation_id', name='uq_queue_confirmation_id'),
    )


class CustodyBalance(Base):
    """
    Custody balance for each account.
    Tracks settled assets and cash.
    """
    __tablename__ = "custody_balances"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Account and instrument
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False)
    custody_type = Column(String(50), default=CustodyType.CASH)
    
    # Balance tracking
    balance = Column(Float, default=0.0)  # Settled amount
    pending_debit = Column(Float, default=0.0)  # Awaiting settlement
    pending_credit = Column(Float, default=0.0)  # Awaiting receipt
    
    # For securities: quantity tracking
    quantity_settled = Column(Float, default=0.0)
    quantity_pending = Column(Float, default=0.0)
    
    # Custody details
    custodian = Column(String(255))  # Bank/custodian name
    custodian_account = Column(String(255))  # Account at custodian
    reference = Column(String(255))  # Custodian reference number
    
    # Reconciliation
    last_reconciled_at = Column(DateTime)
    is_reconciled = Column(Boolean, default=False)
    reconciliation_notes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('account_id', 'instrument_id', name='uq_custody_account_instrument'),
    )


class SettlementRecord(Base):
    """
    Settlement transaction record.
    Permanent record of each settlement.
    """
    __tablename__ = "settlement_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Settlement reference
    settlement_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    
    # Trade confirmation
    trade_confirmation_id = Column(UUID(as_uuid=True), ForeignKey("trade_confirmations.id"), nullable=False)
    
    # Parties
    buyer_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    seller_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    
    # Settlement details
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    settlement_price = Column(Float, nullable=False)
    settlement_amount = Column(Float, nullable=False)
    
    # Payment flows
    buyer_pays = Column(Float, nullable=False)  # Including fees
    seller_receives = Column(Float, nullable=False)  # After fees
    platform_fee_collected = Column(Float, default=0.0)
    
    # Settlement type
    settlement_type = Column(String(50), default=SettlementType.CASH)
    settlement_method = Column(String(50))  # WIRE, ACH, CRYPTO, etc.
    
    # Status
    status = Column(String(50), default=SettlementStatus.SETTLED)
    settlement_date = Column(DateTime, nullable=False)
    actual_settlement_date = Column(DateTime)
    
    # Custody updates
    buyer_custody_updated = Column(Boolean, default=False)
    seller_custody_updated = Column(Boolean, default=False)
    buyer_custody_updated_at = Column(DateTime)
    seller_custody_updated_at = Column(DateTime)
    
    # Broker payout
    broker_paid = Column(Boolean, default=False)
    broker_paid_at = Column(DateTime)
    broker_payment_reference = Column(String(255))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Notes
    notes = Column(Text)


class NetSettlementBatch(Base):
    """
    Net settlement batch.
    Groups multiple trades for net settlement.
    """
    __tablename__ = "net_settlement_batches"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Batch details
    batch_number = Column(String(255), unique=True)
    batch_date = Column(DateTime, nullable=False)
    settlement_date = Column(DateTime, nullable=False)
    
    # Scope
    account_id = Column(Integer, ForeignKey("accounts.id"))  # Optional: specific account batch
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.id"))  # Optional: specific instrument batch
    
    # Trade aggregation
    trade_count = Column(Integer, default=0)
    gross_amount = Column(Float, default=0.0)
    fees_collected = Column(Float, default=0.0)
    net_amount = Column(Float, default=0.0)
    
    # Netting algorithm results
    buy_quantity = Column(Float, default=0.0)
    sell_quantity = Column(Float, default=0.0)
    net_quantity = Column(Float, default=0.0)
    net_price = Column(Float, default=0.0)  # Weighted average price
    
    # Status
    status = Column(String(50), default=SettlementStatus.PENDING)
    is_finalized = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    finalized_at = Column(DateTime)
    
    # Notes
    notes = Column(Text)


class SettlementException(Base):
    """
    Settlement exception tracking.
    For failed settlements and manual interventions.
    """
    __tablename__ = "settlement_exceptions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Exception reference
    exception_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    
    # Related settlement
    settlement_record_id = Column(Integer, ForeignKey("settlement_records.id"))
    trade_confirmation_id = Column(UUID(as_uuid=True), ForeignKey("trade_confirmations.id"))
    
    # Exception details
    exception_type = Column(String(100), nullable=False)  # e.g., "insufficient_funds", "account_closed"
    severity = Column(String(50))  # "low", "medium", "high", "critical"
    description = Column(Text, nullable=False)
    
    # Affected parties
    affected_account_id = Column(Integer, ForeignKey("accounts.id"))
    
    # Resolution
    is_resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text)
    resolved_by = Column(String(255))  # User/system that resolved
    resolved_at = Column(DateTime)
    
    # Timestamps
    detected_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReconciliationReport(Base):
    """
    Reconciliation report between internal ledger and custody/broker records.
    """
    __tablename__ = "reconciliation_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Report details
    report_date = Column(DateTime, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Scope
    account_id = Column(Integer, ForeignKey("accounts.id"))  # Optional: specific account
    custodian = Column(String(255))  # Optional: specific custodian
    
    # Reconciliation results
    expected_balance = Column(Float)
    actual_balance = Column(Float)
    difference = Column(Float)
    is_balanced = Column(Boolean, default=False)
    
    # Trade reconciliation
    expected_trade_count = Column(Integer)
    actual_trade_count = Column(Integer)
    matched_trades = Column(Integer)
    unmatched_trades = Column(Integer)
    
    # Status
    status = Column(String(50))  # "pending", "in_progress", "complete", "exception"
    
    # Report content
    details = Column(Text)  # JSON details of discrepancies
    exceptions = Column(Text)  # JSON array of exceptions
    
    # Approval
    reviewed_by = Column(String(255))
    reviewed_at = Column(DateTime)
    approved = Column(Boolean, default=False)
    
    # Timestamps
    generated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
