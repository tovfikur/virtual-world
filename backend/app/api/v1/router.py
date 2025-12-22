"""
API v1 Router
Aggregates all v1 endpoint routers
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    lands,
    chunks,
    marketplace,
    websocket,
    webrtc,
    chat,
    payments,
    admin,
    trading,
    instruments,
    orders,
    trades,
    market,
    marketdata,
    marketdata_ws,
)

# Create main API router
api_router = APIRouter()

# Include REST endpoint routers
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(lands.router)
api_router.include_router(chunks.router)
api_router.include_router(marketplace.router)
api_router.include_router(chat.router)
api_router.include_router(payments.router)
api_router.include_router(admin.router)
api_router.include_router(trading.router)
api_router.include_router(instruments.router)
api_router.include_router(orders.router)
api_router.include_router(trades.router)
api_router.include_router(market.router)
api_router.include_router(marketdata.router)

# Include WebSocket routers
api_router.include_router(websocket.router)
api_router.include_router(webrtc.router)
api_router.include_router(marketdata_ws.router)
