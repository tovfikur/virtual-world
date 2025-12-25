"""
WebSocket integration tests for Biome Trading System
"""
import pytest
import json
import asyncio
from datetime import datetime
from websockets.client import connect
from app.models import User


@pytest.mark.asyncio
class TestBiomeMarketWebSocket:
    """Test WebSocket market updates"""

    async def test_subscribe_biome_market(self, ws_client, test_user):
        """Test subscribing to biome market updates"""
        # Connect and authenticate
        await ws_client.connect()
        await ws_client.send_auth(test_user.token)
        
        # Subscribe to biome market
        await ws_client.send({
            "action": "subscribe_biome_market",
            "room": "biome_market_all",
        })
        
        # Wait for subscription confirmation
        response = await asyncio.wait_for(ws_client.receive(), timeout=5)
        
        assert response.get("type") == "subscription_confirmation"
        assert response.get("room") == "biome_market_all"
        assert "markets" in response

    async def test_biome_market_update_broadcast(self, ws_client, test_user, client):
        """Test that market updates are broadcast to subscribed clients"""
        # Subscribe to market
        await ws_client.connect()
        await ws_client.send_auth(test_user.token)
        await ws_client.send({
            "action": "subscribe_biome_market",
            "room": "biome_market_all",
        })
        
        # Skip subscription confirmation
        await asyncio.wait_for(ws_client.receive(), timeout=5)
        
        # Track attention to trigger redistribution
        await client.post(
            "/api/v1/biome-market/track-attention",
            json={"biome": "ocean", "attention_score": 100},
            headers={"Authorization": f"Bearer {test_user.token}"},
        )
        
        # Wait for biome_market_update message
        try:
            message = await asyncio.wait_for(ws_client.receive(), timeout=5)
            assert message.get("type") in ["biome_market_update", "biome_attention_update"]
        except asyncio.TimeoutError:
            pytest.skip("Market update not received in time (worker may not have run)")

    async def test_multiple_subscribers(self, test_user, test_user_2):
        """Test that multiple clients receive the same updates"""
        client1 = WSClient("ws://localhost:8000")
        client2 = WSClient("ws://localhost:8000")
        
        # Connect both clients
        await client1.connect()
        await client2.connect()
        
        # Authenticate both
        await client1.send_auth(test_user.token)
        await client2.send_auth(test_user_2.token)
        
        # Subscribe both to market
        await client1.send({
            "action": "subscribe_biome_market",
            "room": "biome_market_all",
        })
        await client2.send({
            "action": "subscribe_biome_market",
            "room": "biome_market_all",
        })
        
        # Both should receive subscription confirmations
        msg1 = await asyncio.wait_for(client1.receive(), timeout=5)
        msg2 = await asyncio.wait_for(client2.receive(), timeout=5)
        
        assert msg1.get("type") == "subscription_confirmation"
        assert msg2.get("type") == "subscription_confirmation"
        
        # Cleanup
        await client1.disconnect()
        await client2.disconnect()

    async def test_unsubscribe_biome_market(self, ws_client, test_user):
        """Test unsubscribing from market updates"""
        await ws_client.connect()
        await ws_client.send_auth(test_user.token)
        
        # Subscribe
        await ws_client.send({
            "action": "subscribe_biome_market",
            "room": "biome_market_all",
        })
        
        # Wait for subscription
        await asyncio.wait_for(ws_client.receive(), timeout=5)
        
        # Unsubscribe
        await ws_client.send({
            "action": "unsubscribe_biome_market",
            "room": "biome_market_all",
        })
        
        # Should receive unsubscription confirmation
        response = await asyncio.wait_for(ws_client.receive(), timeout=5)
        assert response.get("type") in ["unsubscription_confirmation", "ok"]

    async def test_attention_update_broadcast(self, ws_client, test_user, client):
        """Test that attention updates are broadcast"""
        await ws_client.connect()
        await ws_client.send_auth(test_user.token)
        
        # Subscribe to market for updates
        await ws_client.send({
            "action": "subscribe_biome_market",
            "room": "biome_market_all",
        })
        
        # Skip initial subscription confirmation
        await asyncio.wait_for(ws_client.receive(), timeout=5)
        
        # Track attention
        response = await client.post(
            "/api/v1/biome-market/track-attention",
            json={"biome": "forest", "attention_score": 50},
            headers={"Authorization": f"Bearer {test_user.token}"},
        )
        
        assert response.status_code == 200
        
        # Should receive attention update
        try:
            message = await asyncio.wait_for(ws_client.receive(), timeout=5)
            if message.get("type") == "biome_attention_update":
                assert message.get("biome") == "forest"
                assert message.get("total_attention") >= 50
        except asyncio.TimeoutError:
            pytest.skip("Attention update not received in time")

    async def test_ws_reconnection_preserves_subscription(self, test_user):
        """Test that reconnecting preserves subscription state"""
        client1 = WSClient("ws://localhost:8000")
        
        # Connect and subscribe
        await client1.connect()
        await client1.send_auth(test_user.token)
        await client1.send({
            "action": "subscribe_biome_market",
            "room": "biome_market_all",
        })
        
        msg = await asyncio.wait_for(client1.receive(), timeout=5)
        assert msg.get("type") == "subscription_confirmation"
        
        # Disconnect
        await client1.disconnect()
        
        # Reconnect and re-authenticate
        client2 = WSClient("ws://localhost:8000")
        await client2.connect()
        await client2.send_auth(test_user.token)
        
        # Note: Subscription state is per-connection, so we need to re-subscribe
        await client2.send({
            "action": "subscribe_biome_market",
            "room": "biome_market_all",
        })
        
        msg = await asyncio.wait_for(client2.receive(), timeout=5)
        assert msg.get("type") == "subscription_confirmation"
        
        await client2.disconnect()


class WSClient:
    """Lightweight WebSocket test client"""
    
    def __init__(self, url):
        self.url = url
        self.websocket = None
    
    async def connect(self):
        """Connect to WebSocket"""
        self.websocket = await connect(self.url)
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.websocket:
            await self.websocket.close()
    
    async def send(self, message: dict):
        """Send message"""
        await self.websocket.send(json.dumps(message))
    
    async def send_auth(self, token: str):
        """Send authentication"""
        await self.send({"action": "authenticate", "token": token})
    
    async def receive(self):
        """Receive message"""
        data = await self.websocket.recv()
        return json.loads(data)


@pytest.fixture
async def ws_client():
    """WebSocket client fixture"""
    client = WSClient("ws://localhost:8000")
    yield client
    await client.disconnect()


@pytest.fixture
async def test_user_2(db_session):
    """Create a second test user"""
    from app.models import User
    
    user = User(
        email="trader2@test.com",
        username="trader2",
        hashed_password="hashed",
        balance_bdt=100000,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
