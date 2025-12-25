"""
Tests for Biome Trading System
"""
import pytest
import json
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.main import app
from app.models import User, BiomeMarket, BiomeHolding, Transaction
from app.schemas.biome_trading_schema import (
    BiomeMarketResponse,
    TransactionType,
    BiomeTradingRequest,
    BiomePortfolioResponse,
)
from app.services.biome_market_service import BiomeMarketService
from app.services.biome_trading_service import BiomeTradingService
from app.services.attention_tracking_service import AttentionTrackingService
from app.models.transaction import TransactionType as DBTransactionType


@pytest.fixture
async def biome_market_service(db_session: AsyncSession):
    """Initialize biome market service"""
    return BiomeMarketService(db_session)


@pytest.fixture
async def biome_trading_service(db_session: AsyncSession):
    """Initialize biome trading service"""
    return BiomeTradingService(db_session)


@pytest.fixture
async def attention_service(db_session: AsyncSession):
    """Initialize attention tracking service"""
    return AttentionTrackingService(db_session)


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user"""
    user = User(
        email="trader@test.com",
        username="trader",
        hashed_password="hashed",
        balance_bdt=100000,  # Start with 100k BDT
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestBiomeMarketInitialization:
    """Test market initialization"""

    async def test_initialize_markets(self, biome_market_service):
        """Test that all 7 biome markets are initialized correctly"""
        markets = await biome_market_service.initialize_markets()
        
        assert len(markets) == 7
        expected_biomes = [
            "ocean", "beach", "plains", "forest", "desert", "mountain", "snow"
        ]
        
        for biome in expected_biomes:
            market = next((m for m in markets if m.biome == biome), None)
            assert market is not None
            assert market.current_price_bdt == Decimal("100.00")
            assert market.market_cash_bdt >= 0
            assert market.total_shares >= 0


@pytest.mark.asyncio
class TestBiomeTrading:
    """Test buying and selling biome shares"""

    async def test_buy_shares(
        self,
        db_session: AsyncSession,
        biome_trading_service,
        biome_market_service,
        test_user,
    ):
        """Test buying biome shares"""
        # Initialize markets
        await biome_market_service.initialize_markets()
        
        # Buy 100 ocean shares at starting price of 100 BDT each
        initial_balance = test_user.balance_bdt
        buy_amount = Decimal("10000")  # 10,000 BDT = 100 shares at 100 BDT/share
        
        transaction = await biome_trading_service.buy_shares(
            user_id=test_user.id,
            biome="ocean",
            amount_bdt=buy_amount,
        )
        
        assert transaction is not None
        assert transaction.biome == "ocean"
        assert transaction.transaction_type == DBTransactionType.BIOME_BUY
        assert transaction.amount_bdt == buy_amount
        
        # Verify user balance decreased
        await db_session.refresh(test_user)
        assert test_user.balance_bdt == initial_balance - buy_amount
        
        # Verify holding created
        holding = await db_session.execute(
            f"SELECT * FROM biome_holdings WHERE user_id = {test_user.id} AND biome = 'ocean'"
        )

    async def test_sell_shares(
        self,
        db_session: AsyncSession,
        biome_trading_service,
        biome_market_service,
        test_user,
    ):
        """Test selling biome shares"""
        # Initialize markets
        await biome_market_service.initialize_markets()
        
        # First buy shares
        await biome_trading_service.buy_shares(
            user_id=test_user.id,
            biome="forest",
            amount_bdt=Decimal("5000"),
        )
        
        initial_balance = test_user.balance_bdt
        
        # Now sell some shares (50 shares at 100 BDT = 5000 BDT)
        transaction = await biome_trading_service.sell_shares(
            user_id=test_user.id,
            biome="forest",
            shares=50,
        )
        
        assert transaction is not None
        assert transaction.biome == "forest"
        assert transaction.transaction_type == DBTransactionType.BIOME_SELL
        
        # Verify user balance increased
        await db_session.refresh(test_user)
        assert test_user.balance_bdt > initial_balance

    async def test_insufficient_balance(
        self,
        biome_trading_service,
        biome_market_service,
        test_user,
    ):
        """Test buying with insufficient balance"""
        await biome_market_service.initialize_markets()
        
        with pytest.raises(ValueError, match="Insufficient balance"):
            await biome_trading_service.buy_shares(
                user_id=test_user.id,
                biome="ocean",
                amount_bdt=Decimal("1000000"),  # More than user balance
            )


@pytest.mark.asyncio
class TestAttentionTracking:
    """Test attention tracking and redistribution"""

    async def test_track_attention(
        self,
        attention_service,
        test_user,
    ):
        """Test tracking user attention"""
        attention_score = 50
        
        result = await attention_service.track_attention(
            user_id=test_user.id,
            biome="plains",
            attention_score=attention_score,
        )
        
        assert result is not None
        assert result.biome == "plains"
        assert result.user_id == test_user.id
        assert result.attention_score == attention_score

    async def test_get_user_attention(
        self,
        attention_service,
        test_user,
    ):
        """Test retrieving user attention across biomes"""
        # Track attention on multiple biomes
        for biome in ["ocean", "forest", "desert"]:
            await attention_service.track_attention(
                user_id=test_user.id,
                biome=biome,
                attention_score=25,
            )
        
        attentions = await attention_service.get_user_attention(test_user.id)
        
        assert len(attentions) == 3
        assert all(att.attention_score == 25 for att in attentions)


@pytest.mark.asyncio
class TestBiomeMarketAPI:
    """Test REST API endpoints"""

    async def test_get_all_markets(self, client: AsyncClient, test_user):
        """Test GET /biome-market/markets"""
        response = await client.get(
            "/api/v1/biome-market/markets",
            headers={"Authorization": f"Bearer {test_user.token}"},
        )
        
        assert response.status_code == 200
        markets = response.json()
        assert len(markets) == 7
        assert all(m["biome"] in [
            "ocean", "beach", "plains", "forest", "desert", "mountain", "snow"
        ] for m in markets)

    async def test_get_single_market(self, client: AsyncClient, test_user):
        """Test GET /biome-market/markets/{biome}"""
        response = await client.get(
            "/api/v1/biome-market/markets/ocean",
            headers={"Authorization": f"Bearer {test_user.token}"},
        )
        
        assert response.status_code == 200
        market = response.json()
        assert market["biome"] == "ocean"
        assert "current_price_bdt" in market
        assert "market_cash_bdt" in market
        assert "total_attention" in market

    async def test_get_price_history(self, client: AsyncClient, test_user):
        """Test GET /biome-market/price-history/{biome}"""
        response = await client.get(
            "/api/v1/biome-market/price-history/forest?hours=24",
            headers={"Authorization": f"Bearer {test_user.token}"},
        )
        
        assert response.status_code == 200
        history = response.json()
        assert isinstance(history, list)

    async def test_buy_shares_endpoint(self, client: AsyncClient, test_user):
        """Test POST /biome-market/buy"""
        response = await client.post(
            "/api/v1/biome-market/buy",
            json={
                "biome": "ocean",
                "amount_bdt": "5000",
            },
            headers={"Authorization": f"Bearer {test_user.token}"},
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["biome"] == "ocean"
        assert result["transaction_type"] == "BUY"

    async def test_sell_shares_endpoint(self, client: AsyncClient, test_user):
        """Test POST /biome-market/sell"""
        # First buy shares
        await client.post(
            "/api/v1/biome-market/buy",
            json={
                "biome": "mountain",
                "amount_bdt": "5000",
            },
            headers={"Authorization": f"Bearer {test_user.token}"},
        )
        
        # Then sell
        response = await client.post(
            "/api/v1/biome-market/sell",
            json={
                "biome": "mountain",
                "shares": 25,
            },
            headers={"Authorization": f"Bearer {test_user.token}"},
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["biome"] == "mountain"
        assert result["transaction_type"] == "SELL"

    async def test_get_portfolio(self, client: AsyncClient, test_user):
        """Test GET /biome-market/portfolio"""
        # Make some trades first
        await client.post(
            "/api/v1/biome-market/buy",
            json={"biome": "ocean", "amount_bdt": "5000"},
            headers={"Authorization": f"Bearer {test_user.token}"},
        )
        
        response = await client.get(
            "/api/v1/biome-market/portfolio",
            headers={"Authorization": f"Bearer {test_user.token}"},
        )
        
        assert response.status_code == 200
        portfolio = response.json()
        assert "total_invested_bdt" in portfolio
        assert "current_value_bdt" in portfolio
        assert "unrealized_gain_bdt" in portfolio
        assert "holdings" in portfolio

    async def test_get_transaction_history(self, client: AsyncClient, test_user):
        """Test GET /biome-market/transactions"""
        response = await client.get(
            "/api/v1/biome-market/transactions",
            headers={"Authorization": f"Bearer {test_user.token}"},
        )
        
        assert response.status_code == 200
        transactions = response.json()
        assert isinstance(transactions, list)

    async def test_track_attention_endpoint(self, client: AsyncClient, test_user):
        """Test POST /biome-market/track-attention"""
        response = await client.post(
            "/api/v1/biome-market/track-attention",
            json={
                "biome": "desert",
                "attention_score": 75,
            },
            headers={"Authorization": f"Bearer {test_user.token}"},
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result["biome"] == "desert"
        assert result["total_attention"] >= 75
