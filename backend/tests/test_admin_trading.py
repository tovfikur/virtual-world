"""
Tests for Admin, Broker, and Surveillance services.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.account import Account
from app.models.instrument import Instrument
from app.models.order import Order, OrderStatus, OrderSide
from app.models.trade import Trade
from app.models.admin import (
    AdminUser, InstrumentControl, MarketControl, 
    RiskConfigurable, FeeConfig, BrokerAccount,
    SurveillanceAlert, AdminRole, BrokerType
)
from app.services.admin_service import AdminService
from app.services.broker_service import BrokerService
from app.services.surveillance_service import SurveillanceService


@pytest.fixture
async def test_db():
    """Create in-memory test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_delete=False)
    
    async with SessionLocal() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
def admin_service():
    """Create AdminService instance."""
    return AdminService()


@pytest.fixture
def broker_service():
    """Create BrokerService instance."""
    return BrokerService()


@pytest.fixture
def surveillance_service():
    """Create SurveillanceService instance."""
    return SurveillanceService()


@pytest.fixture
async def test_account(test_db):
    """Create a test trading account."""
    account = Account(
        email="test@example.com",
        username="testuser",
        hashed_password="hashed",
        is_active=True
    )
    test_db.add(account)
    await test_db.flush()
    return account


@pytest.fixture
async def test_instrument(test_db):
    """Create a test instrument."""
    instrument = Instrument(
        symbol="BTC/USD",
        name="Bitcoin",
        asset_class="crypto",
        base_currency="BTC",
        quote_currency="USD",
        contract_size=1.0,
        tick_size=0.01,
        is_tradable=True
    )
    test_db.add(instrument)
    await test_db.flush()
    return instrument


@pytest.fixture
async def test_admin_user(test_db, test_account):
    """Create a test admin user."""
    admin = AdminUser(
        account_id=test_account.id,
        role=AdminRole.ADMIN,
        is_active=True,
        created_at=datetime.utcnow()
    )
    test_db.add(admin)
    await test_db.flush()
    return admin


class TestAdminService:
    """Test AdminService functionality."""
    
    @pytest.mark.asyncio
    async def test_get_instrument_control(self, admin_service, test_db, test_instrument):
        """Test retrieving instrument control settings."""
        control = await admin_service.get_instrument_control(test_instrument.id, test_db)
        assert control is not None
        assert control.instrument_id == test_instrument.id
    
    @pytest.mark.asyncio
    async def test_halt_instrument(self, admin_service, test_db, test_instrument, test_admin_user):
        """Test halting an instrument."""
        control = await admin_service.halt_instrument(
            test_instrument.id,
            duration_minutes=30,
            reason="Circuit breaker triggered",
            admin_id=test_admin_user.account_id,
            db=test_db
        )
        
        assert control.is_halted == True
        assert control.halt_reason == "Circuit breaker triggered"
        assert control.halted_until is not None
    
    @pytest.mark.asyncio
    async def test_resume_instrument(self, admin_service, test_db, test_instrument, test_admin_user):
        """Test resuming a halted instrument."""
        # First halt
        await admin_service.halt_instrument(
            test_instrument.id,
            30,
            "Test halt",
            test_admin_user.account_id,
            test_db
        )
        
        # Then resume
        control = await admin_service.resume_instrument(
            test_instrument.id,
            test_admin_user.account_id,
            test_db
        )
        
        assert control.is_halted == False
        assert control.is_trading_enabled == True
    
    @pytest.mark.asyncio
    async def test_update_instrument_limits(self, admin_service, test_db, test_instrument, test_admin_user):
        """Test updating instrument limits."""
        control = await admin_service.update_instrument_limits(
            test_instrument.id,
            max_order_size=10000.0,
            max_daily_volume=50000.0,
            max_leverage=20.0,
            admin_id=test_admin_user.account_id,
            db=test_db
        )
        
        assert float(control.max_order_size) == 10000.0
        assert float(control.max_daily_volume) == 50000.0
        assert float(control.max_leverage) == 20.0
    
    @pytest.mark.asyncio
    async def test_get_market_control(self, admin_service, test_db):
        """Test retrieving market control status."""
        control = await admin_service.get_market_control(test_db)
        assert control is not None
        assert hasattr(control, 'market_open')
        assert hasattr(control, 'market_halted')
    
    @pytest.mark.asyncio
    async def test_halt_market(self, admin_service, test_db, test_admin_user):
        """Test halting the entire market."""
        control = await admin_service.halt_market(
            duration_minutes=60,
            reason="System maintenance",
            admin_id=test_admin_user.account_id,
            db=test_db
        )
        
        assert control.market_halted == True
        assert control.halt_reason == "System maintenance"
    
    @pytest.mark.asyncio
    async def test_resume_market(self, admin_service, test_db, test_admin_user):
        """Test resuming the market."""
        # First halt
        await admin_service.halt_market(60, "Test halt", test_admin_user.account_id, test_db)
        
        # Then resume
        control = await admin_service.resume_market(test_admin_user.account_id, test_db)
        assert control.market_halted == False
    
    @pytest.mark.asyncio
    async def test_get_risk_config(self, admin_service, test_db):
        """Test retrieving risk configuration."""
        config = await admin_service.get_risk_config(test_db)
        assert config is not None
        assert hasattr(config, 'maintenance_margin')
        assert hasattr(config, 'initial_margin')
        assert hasattr(config, 'liquidation_threshold')
    
    @pytest.mark.asyncio
    async def test_update_risk_config(self, admin_service, test_db, test_admin_user):
        """Test updating risk configuration."""
        config = await admin_service.update_risk_config(
            maintenance_margin=0.15,
            initial_margin=0.20,
            liquidation_threshold=0.95,
            max_position_size=100000.0,
            admin_id=test_admin_user.account_id,
            db=test_db
        )
        
        assert float(config.maintenance_margin) == 0.15
        assert float(config.initial_margin) == 0.20
    
    @pytest.mark.asyncio
    async def test_get_fee_config(self, admin_service, test_db):
        """Test retrieving fee configuration."""
        config = await admin_service.get_fee_config(test_db)
        assert config is not None
        assert hasattr(config, 'maker_fee')
        assert hasattr(config, 'taker_fee')
    
    @pytest.mark.asyncio
    async def test_update_fee_config(self, admin_service, test_db, test_admin_user):
        """Test updating fee configuration."""
        config = await admin_service.update_fee_config(
            maker_fee=0.0001,
            taker_fee=0.0005,
            funding_fee=0.00015,
            swap_fee=0.0002,
            admin_id=test_admin_user.account_id,
            db=test_db
        )
        
        assert float(config.maker_fee) == 0.0001
        assert float(config.taker_fee) == 0.0005


class TestBrokerService:
    """Test BrokerService functionality."""
    
    @pytest.mark.asyncio
    async def test_create_broker_account(self, broker_service, test_db):
        """Test creating a new broker account."""
        broker = await broker_service.create_broker_account(
            name="Test Broker",
            broker_type=BrokerType.A_BOOK,
            credit_limit=1000000.0,
            db=test_db
        )
        
        assert broker.name == "Test Broker"
        assert broker.broker_type == BrokerType.A_BOOK
        assert float(broker.credit_limit) == 1000000.0
        assert broker.api_key is not None
        assert broker.broker_id is not None
    
    @pytest.mark.asyncio
    async def test_get_broker_account(self, broker_service, test_db):
        """Test retrieving a broker account."""
        # Create broker
        created = await broker_service.create_broker_account(
            "Test Broker",
            BrokerType.B_BOOK,
            500000.0,
            test_db
        )
        
        # Retrieve by ID
        broker = await broker_service.get_broker_account(broker_id=created.broker_id, db=test_db)
        assert broker is not None
        assert broker.name == "Test Broker"
    
    @pytest.mark.asyncio
    async def test_create_sub_account(self, broker_service, test_db, test_account):
        """Test creating a broker sub-account."""
        # Create broker
        broker = await broker_service.create_broker_account(
            "Test Broker",
            BrokerType.A_BOOK,
            1000000.0,
            test_db
        )
        
        # Create sub-account
        sub = await broker_service.create_sub_account(
            broker.broker_id,
            test_account.id,
            commission_share=0.5,
            db=test_db
        )
        
        assert sub.broker_id == broker.broker_id
        assert sub.account_id == test_account.id
        assert sub.commission_share == 0.5
    
    @pytest.mark.asyncio
    async def test_check_credit_limit(self, broker_service, test_db):
        """Test credit limit checking."""
        broker = await broker_service.create_broker_account(
            "Test Broker",
            BrokerType.A_BOOK,
            100000.0,
            test_db
        )
        
        # Check available credit
        available = await broker_service.check_credit_limit(broker.broker_id, test_db)
        assert available == 100000.0
    
    @pytest.mark.asyncio
    async def test_utilize_and_release_credit(self, broker_service, test_db):
        """Test credit utilization and release."""
        broker = await broker_service.create_broker_account(
            "Test Broker",
            BrokerType.A_BOOK,
            100000.0,
            test_db
        )
        
        # Utilize credit
        await broker_service.utilize_credit(broker.broker_id, 50000.0, test_db)
        available = await broker_service.check_credit_limit(broker.broker_id, test_db)
        assert available == 50000.0
        
        # Release credit
        await broker_service.release_credit(broker.broker_id, 30000.0, test_db)
        available = await broker_service.check_credit_limit(broker.broker_id, test_db)
        assert available == 80000.0
    
    @pytest.mark.asyncio
    async def test_accrue_and_payout_commission(self, broker_service, test_db):
        """Test commission accrual and payout."""
        broker = await broker_service.create_broker_account(
            "Test Broker",
            BrokerType.B_BOOK,
            1000000.0,
            test_db
        )
        
        # Accrue commission
        await broker_service.accrue_commission(broker.broker_id, 5000.0, test_db)
        
        # Check accrual
        accrued = broker.commission_accrued
        assert float(accrued) >= 5000.0
        
        # Payout commission
        await broker_service.payout_commission(broker.broker_id, 3000.0, test_db)
        
        # Verify payout
        paid = broker.commission_paid
        assert float(paid) >= 3000.0


class TestSurveillanceService:
    """Test SurveillanceService anomaly detection."""
    
    @pytest.mark.asyncio
    async def test_detect_spoofing(self, surveillance_service, test_db, test_account, test_instrument):
        """Test spoofing detection."""
        # Create cancelled orders
        for i in range(5):
            order = Order(
                account_id=test_account.id,
                instrument_id=test_instrument.id,
                side=OrderSide.BUY,
                order_type="limit",
                quantity=100.0,
                price=50000.0,
                status=OrderStatus.CANCELLED,
                created_at=datetime.utcnow()
            )
            test_db.add(order)
        
        # Create one filled order
        filled = Order(
            account_id=test_account.id,
            instrument_id=test_instrument.id,
            side=OrderSide.BUY,
            order_type="limit",
            quantity=100.0,
            price=50000.0,
            status=OrderStatus.FILLED,
            created_at=datetime.utcnow()
        )
        test_db.add(filled)
        await test_db.flush()
        
        # Detect spoofing
        alert = await surveillance_service.detect_spoofing(
            test_account.id,
            test_instrument.id,
            db=test_db
        )
        
        assert alert is not None
        assert alert.severity == "high"
        assert alert.anomaly_type == "spoofing"
    
    @pytest.mark.asyncio
    async def test_get_active_alerts(self, surveillance_service, test_db, test_account, test_instrument):
        """Test retrieving active alerts."""
        # Create an alert
        alert = SurveillanceAlert(
            anomaly_type="spoofing",
            severity="medium",
            account_id=test_account.id,
            instrument_id=test_instrument.id,
            description="Test alert",
            evidence={"test": "data"},
            detected_at=datetime.utcnow()
        )
        test_db.add(alert)
        await test_db.flush()
        
        # Get active alerts
        alerts = await surveillance_service.get_active_alerts(
            account_id=test_account.id,
            db=test_db
        )
        
        assert len(alerts) > 0
        assert alerts[0].account_id == test_account.id
    
    @pytest.mark.asyncio
    async def test_resolve_alert(self, surveillance_service, test_db, test_account, test_instrument):
        """Test resolving an alert."""
        # Create an alert
        alert = SurveillanceAlert(
            anomaly_type="wash_trade",
            severity="critical",
            account_id=test_account.id,
            instrument_id=test_instrument.id,
            description="Test alert",
            evidence={},
            detected_at=datetime.utcnow()
        )
        test_db.add(alert)
        await test_db.flush()
        alert_id = alert.id
        
        # Resolve alert
        resolved = await surveillance_service.resolve_alert(
            alert_id,
            resolution="Account flagged for review",
            resolved_by="admin123",
            db=test_db
        )
        
        assert resolved.is_resolved == True
        assert resolved.resolution == "Account flagged for review"
        assert resolved.resolved_at is not None


class TestAdminPermissions:
    """Test admin role-based permissions."""
    
    @pytest.mark.asyncio
    async def test_verify_admin_permission(self, admin_service, test_db, test_admin_user):
        """Test admin permission verification."""
        # Should have permission as ADMIN
        try:
            await admin_service.verify_admin_permission(
                AdminRole.ADMIN,
                test_admin_user.role,
                test_db
            )
        except Exception as e:
            pytest.fail(f"Permission check failed: {e}")
    
    @pytest.mark.asyncio
    async def test_role_hierarchy(self, test_db):
        """Test role hierarchy (higher roles can perform lower role actions)."""
        viewer = AdminRole.VIEWER
        operator = AdminRole.OPERATOR
        admin = AdminRole.ADMIN
        super_admin = AdminRole.SUPER_ADMIN
        
        # Super admin should be highest
        assert super_admin.value > admin.value
        assert admin.value > operator.value
        assert operator.value > viewer.value
