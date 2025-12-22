"""
Admin, broker, and compliance models.
Handles administrative controls, broker sub-accounts, and regulatory compliance.
"""

from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Boolean, Enum, Text, UniqueConstraint, DECIMAL
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.db.base import Base


class AdminRole(str, enum.Enum):
    """Administrator role levels."""
    VIEWER = "viewer"           # Read-only access
    OPERATOR = "operator"       # Can halt/resume but not change config
    ADMIN = "admin"             # Full administrative access
    SUPER_ADMIN = "super_admin" # All access including user management


class BrokerType(str, enum.Enum):
    """Broker account types."""
    PRIME_BROKER = "prime_broker"     # Large volume aggregator
    RETAIL_BROKER = "retail_broker"   # Retail client broker
    DEALING_DESK = "dealing_desk"     # Market maker/dealer
    CUSTODIAN = "custodian"           # Asset custodian


class BookType(str, enum.Enum):
    """Broker booking types."""
    A_BOOK = "a_book"           # Broker passes through to market
    B_BOOK = "b_book"           # Broker takes other side (risk)
    HYBRID = "hybrid"           # Mix of A and B booking


class AnomalyType(str, enum.Enum):
    """Market anomaly types for surveillance."""
    SPOOFING = "spoofing"                    # Orders placed to manipulate
    WASH_TRADE = "wash_trade"               # Same party buy/sell
    FRONT_RUNNING = "front_running"        # Insider trading pattern
    LAYERING = "layering"                  # Multiple fake orders
    QUOTE_STUFFING = "quote_stuffing"      # Excessive order cancellations
    PRICE_MANIPULATION = "price_manipulation"  # Artificial price movement
    UNUSUAL_VOLUME = "unusual_volume"      # Abnormal trade activity


class AdminUser(Base):
    """Administrator user account."""
    __tablename__ = "admin_users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User details
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255))
    
    # Authentication
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Authorization
    role = Column(String(50), default=AdminRole.VIEWER)
    permissions = Column(JSON, default={})  # Fine-grained permissions
    
    # Activity tracking
    last_login = Column(DateTime)
    login_count = Column(Integer, default=0)
    failed_login_attempts = Column(Integer, default=0)
    last_failed_login = Column(DateTime)
    
    # Audit trail
    created_by = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Status
    notes = Column(Text)


class InstrumentControl(Base):
    """Instrument-level administrative controls."""
    __tablename__ = "instrument_controls"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Instrument
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.instrument_id"), nullable=False, unique=True)
    
    # Trading controls
    is_trading_enabled = Column(Boolean, default=True)
    trading_disabled_at = Column(DateTime)
    trading_disabled_reason = Column(String(255))
    
    # Circuit breaker settings
    circuit_breaker_enabled = Column(Boolean, default=True)
    price_move_threshold = Column(Float, default=5.0)  # % movement to trigger
    volume_surge_threshold = Column(Float, default=200.0)  # % above avg
    halted_until = Column(DateTime)  # Halt expiration
    
    # Order restrictions
    max_order_size = Column(Float)  # Per order limit
    max_daily_volume = Column(Float)  # Daily volume cap
    max_leverage = Column(Float)
    min_order_size = Column(Float)
    
    # Tick and lot controls
    tick_size = Column(Float)  # Can override default
    lot_size = Column(Float)   # Can override default
    
    # Trading hours
    market_open_time = Column(String(5))  # HH:MM
    market_close_time = Column(String(5))
    market_holidays = Column(JSON, default=[])  # List of holiday dates
    
    # Settlement
    settlement_days = Column(Integer, default=2)  # T+N
    
    # Custody
    enable_physical_delivery = Column(Boolean, default=False)
    custodian = Column(String(255))
    
    # Risk parameters
    margin_requirement = Column(Float, default=0.25)
    position_limit = Column(Float)
    
    # Status
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MarketControl(Base):
    """Market-wide administrative controls."""
    __tablename__ = "market_controls"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Market state
    market_open = Column(Boolean, default=True)
    closed_reason = Column(String(255))
    closed_until = Column(DateTime)
    
    # Global circuit breaker
    global_circuit_breaker_enabled = Column(Boolean, default=True)
    global_price_move_threshold = Column(Float, default=10.0)  # % market movement
    global_volume_threshold = Column(Float, default=500.0)  # Contracts per minute
    
    # Order restrictions
    max_orders_per_minute = Column(Integer, default=10000)
    max_cancel_per_minute = Column(Integer, default=5000)
    
    # Leverage limits
    max_system_leverage = Column(Float, default=100.0)
    
    # Fees
    transaction_fee = Column(Float, default=0.0)  # Additional platform fee
    emergency_fee = Column(Float, default=0.0)  # During stress
    
    # Monitoring
    alert_threshold_orders = Column(Integer, default=1000)  # Per second
    alert_threshold_volume = Column(Float, default=10000.0)  # Per second
    
    # Status
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RiskConfigurable(Base):
    """Configurable risk management parameters."""
    __tablename__ = "risk_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Margin requirements
    default_margin_requirement = Column(Float, default=0.01)  # 1%
    minimum_margin_requirement = Column(Float, default=0.002)  # 0.2%
    maximum_margin_requirement = Column(Float, default=1.0)  # 100%
    
    # Margin call parameters
    margin_call_level = Column(Float, default=1.5)  # 150%
    liquidation_level = Column(Float, default=1.0)  # 100%
    
    # Liquidation
    liquidation_enabled = Column(Boolean, default=True)
    liquidation_cooldown_minutes = Column(Integer, default=5)  # Grace period
    partial_liquidation_enabled = Column(Boolean, default=True)
    partial_liquidation_percentage = Column(Float, default=50.0)  # Close 50% first
    
    # Exposure limits
    max_account_leverage = Column(Float, default=100.0)
    max_position_size = Column(Float)  # Per instrument
    max_concentration = Column(Float, default=20.0)  # Single instrument % of portfolio
    
    # Stress scenarios
    stress_multiplier = Column(Float, default=2.0)  # VaR multiplier
    var_percentile = Column(Float, default=0.99)  # 99th percentile
    
    # Correlated pair limits
    enable_correlation_check = Column(Boolean, default=True)
    correlation_threshold = Column(Float, default=0.8)  # 0.8+ correlation
    
    # Status
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FeeConfig(Base):
    """Configurable fee parameters."""
    __tablename__ = "fee_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Maker/taker fees
    default_maker_fee = Column(Float, default=0.0)
    default_taker_fee = Column(Float, default=0.001)  # 0.1%
    
    # Fee types
    enable_percentage_fees = Column(Boolean, default=True)
    enable_flat_fees = Column(Boolean, default=True)
    enable_per_lot_fees = Column(Boolean, default=True)
    
    # Volume discounts
    enable_volume_tiers = Column(Boolean, default=True)
    volume_tier_threshold_1 = Column(Float, default=1000.0)  # 30-day volume
    volume_tier_discount_1 = Column(Float, default=0.1)  # 10% discount
    volume_tier_threshold_2 = Column(Float, default=10000.0)
    volume_tier_discount_2 = Column(Float, default=0.25)  # 25% discount
    volume_tier_threshold_3 = Column(Float, default=50000.0)
    volume_tier_discount_3 = Column(Float, default=0.5)  # 50% discount
    
    # Swap fees
    overnight_swap_enabled = Column(Boolean, default=True)
    weekend_swap_multiplier = Column(Float, default=3.0)  # Triple on weekends
    
    # Funding rates (perpetuals)
    funding_rate_enabled = Column(Boolean, default=True)
    funding_rate_interval = Column(Integer, default=8)  # Every 8 hours
    base_funding_rate = Column(Float, default=0.0001)  # 0.01%
    max_funding_rate = Column(Float, default=0.005)  # 0.5%
    
    # Promotional fees
    enable_referral_credits = Column(Boolean, default=True)
    referral_credit_percentage = Column(Float, default=0.5)  # 50% commission
    enable_seasonal_discounts = Column(Boolean, default=False)
    seasonal_discount_percentage = Column(Float, default=0.0)
    
    # Status
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BrokerAccount(Base):
    """Broker/dealer account configuration."""
    __tablename__ = "broker_accounts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Broker identity
    broker_name = Column(String(255), nullable=False)
    broker_id = Column(String(50), unique=True, nullable=False)
    broker_type = Column(String(50), default=BrokerType.RETAIL_BROKER)
    
    # Booking arrangement
    default_book_type = Column(String(50), default=BookType.A_BOOK)
    can_hedge = Column(Boolean, default=False)
    hedge_ratio = Column(Float, default=0.5)  # Percentage to hedge
    
    # Commission sharing
    can_share_commission = Column(Boolean, default=False)
    commission_share_percentage = Column(Float, default=0.0)
    payable_commission = Column(Float, default=0.0)  # Accumulated
    
    # Credit limits
    credit_limit = Column(Float, default=0.0)
    current_credit_utilization = Column(Float, default=0.0)
    
    # Sub-accounts
    max_sub_accounts = Column(Integer, default=100)
    current_sub_account_count = Column(Integer, default=0)
    
    # Trading controls
    trading_enabled = Column(Boolean, default=True)
    max_leverage = Column(Float, default=50.0)
    max_daily_trading_limit = Column(Float, default=0.0)  # Unlimited
    
    # API access
    api_key = Column(String(255), unique=True)
    api_secret_hash = Column(String(255))
    api_enabled = Column(Boolean, default=True)
    api_rate_limit = Column(Integer, default=1000)  # Requests per minute
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Contact
    contact_email = Column(String(255))
    contact_phone = Column(String(20))


class SurveillanceAlert(Base):
    """Surveillance alert for suspicious market activity."""
    __tablename__ = "surveillance_alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Alert identity
    alert_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    anomaly_type = Column(String(50), nullable=False)  # Type of anomaly
    severity = Column(String(50), default="medium")  # low, medium, high, critical
    
    # Detected pattern
    account_id = Column(Integer, ForeignKey("accounts.id"))
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.instrument_id"))
    
    # Pattern details
    description = Column(Text, nullable=False)
    evidence = Column(JSON)  # Raw data supporting alert
    
    # Trade details if applicable
    order_ids = Column(JSON)  # Related order IDs
    trade_ids = Column(JSON)  # Related trade IDs
    
    # Status
    is_resolved = Column(Boolean, default=False)
    resolution = Column(Text)  # How it was resolved
    resolved_by = Column(String(255))  # Admin who resolved
    resolved_at = Column(DateTime)
    
    # Escalation
    escalated = Column(Boolean, default=False)
    escalated_to = Column(String(255))  # Regulatory body
    escalated_at = Column(DateTime)
    
    # Timestamps
    detected_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ComplianceReport(Base):
    """Compliance and regulatory reports."""
    __tablename__ = "compliance_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Report metadata
    report_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    report_type = Column(String(100), nullable=False)  # Best execution, tax, etc.
    report_date = Column(DateTime, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Scope
    account_id = Column(Integer, ForeignKey("accounts.id"))  # Optional: specific account
    
    # Report content
    summary = Column(Text)
    detailed_data = Column(JSON)  # Full report data
    
    # Validation
    validated = Column(Boolean, default=False)
    validated_by = Column(String(255))
    validated_at = Column(DateTime)
    
    # Export
    exported = Column(Boolean, default=False)
    export_format = Column(String(50))  # CSV, JSON, PDF
    exported_at = Column(DateTime)
    
    # Status
    status = Column(String(50), default="pending")  # pending, complete, delivered
    recipient = Column(String(255))  # Regulatory body or auditor
    
    # Timestamps
    generated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditAction(Base):
    """Detailed audit log of administrative actions."""
    __tablename__ = "audit_actions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Action metadata
    action_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    action_type = Column(String(100), nullable=False)  # add_instrument, halt_market, etc.
    category = Column(String(50))  # admin, compliance, surveillance
    
    # Actor
    actor_id = Column(Integer, ForeignKey("admin_users.id"))
    actor_username = Column(String(255))
    
    # Target
    target_type = Column(String(50))  # instrument, market, account
    target_id = Column(String(255))  # Instrument ID, account ID, etc.
    
    # Details
    old_value = Column(JSON)  # Before change
    new_value = Column(JSON)  # After change
    description = Column(Text)
    
    # Status
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    
    # Approval (for sensitive actions)
    requires_approval = Column(Boolean, default=False)
    approved_by = Column(Integer, ForeignKey("admin_users.id"))
    approved_at = Column(DateTime)
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String(50))
    user_agent = Column(String(500))


class RegulatoryExemption(Base):
    """Regulatory exemptions or waivers."""
    __tablename__ = "regulatory_exemptions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Exemption details
    exemption_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    exemption_type = Column(String(100), nullable=False)  # leverage_limit, trading_hours, etc.
    reason = Column(String(255), nullable=False)
    
    # Subject
    account_id = Column(Integer, ForeignKey("accounts.id"))
    instrument_id = Column(UUID(as_uuid=True), ForeignKey("instruments.instrument_id"))
    
    # Exemption details
    exemption_value = Column(DECIMAL(10, 4))  # New limit or threshold
    exemption_description = Column(Text)
    
    # Validity
    effective_date = Column(DateTime, nullable=False)
    expiration_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Approval
    approved_by = Column(Integer, ForeignKey("admin_users.id"))
    approved_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255))
