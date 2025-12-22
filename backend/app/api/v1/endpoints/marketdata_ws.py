"""
WebSocket endpoints for real-time market data streaming.
Supports subscriptions to quotes, depth, trades, and candles.
"""

from fastapi import APIRouter, WebSocketDisconnect, WebSocket, Query, Depends
from typing import Optional
import json
import logging
from uuid import UUID

from app.services.websocket_service import market_data_manager
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.instrument import Instrument
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/marketdata")
async def websocket_marketdata(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for market data subscriptions.
    
    Client can send JSON messages to subscribe/unsubscribe:
    {
        "action": "subscribe",
        "channel": "quote:instrument_id"
    }
    
    Supported channels:
    - quote:{instrument_id} - Top-of-book quotes
    - depth:{instrument_id}:{levels} - Order book depth
    - trades:{instrument_id} - Recent trades
    - candles:{instrument_id}:{timeframe} - OHLCV candles
    - status:{instrument_id} - Instrument status
    """
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                action = message.get("action")
                channel = message.get("channel")
                
                if action == "subscribe":
                    if not channel:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": "Channel required for subscribe"
                        }))
                        continue
                    
                    # Validate channel format
                    channel_parts = channel.split(":")
                    if not channel_parts[0] in ["quote", "depth", "trades", "candles", "status"]:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"Invalid channel: {channel_parts[0]}"
                        }))
                        continue
                    
                    # Validate instrument_id if present
                    if len(channel_parts) > 1:
                        try:
                            UUID(channel_parts[1])
                        except ValueError:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": f"Invalid instrument_id: {channel_parts[1]}"
                            }))
                            continue
                    
                    await market_data_manager.subscribe(websocket, channel)
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "channel": channel
                    }))
                    logger.info(f"WebSocket subscribed to {channel}")
                
                elif action == "unsubscribe":
                    if channel:
                        await market_data_manager.unsubscribe(websocket, channel)
                        await websocket.send_text(json.dumps({
                            "type": "unsubscribed",
                            "channel": channel
                        }))
                        logger.info(f"WebSocket unsubscribed from {channel}")
                    else:
                        await market_data_manager.unsubscribe(websocket)
                        await websocket.send_text(json.dumps({
                            "type": "unsubscribed",
                            "message": "Unsubscribed from all channels"
                        }))
                        logger.info(f"WebSocket unsubscribed from all channels")
                
                elif action == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong"
                    }))
                
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    }))
            
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON"
                }))
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": str(e)
                }))
    
    except WebSocketDisconnect:
        # Clean up subscriptions
        await market_data_manager.unsubscribe(websocket)
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await market_data_manager.unsubscribe(websocket)
