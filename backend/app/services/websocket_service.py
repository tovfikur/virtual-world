"""
WebSocket Service
Manages WebSocket connections, rooms, and message broadcasting
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, List, Optional
import asyncio
import json
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and rooms.

    Features:
    - Connection pooling per user
    - Room-based broadcasting
    - Presence tracking
    - Message queuing
    - Automatic cleanup on disconnect
    """

    def __init__(self):
        # Active connections: {user_id: Set[WebSocket]}
        self.active_connections: Dict[str, Set[WebSocket]] = {}

        # Room memberships: {room_id: Set[user_id]}
        self.rooms: Dict[str, Set[str]] = {}

        # User presence: {user_id: {status, last_seen, location}}
        self.presence: Dict[str, dict] = {}

        # WebSocket to user mapping for quick lookup
        self.websocket_to_user: Dict[WebSocket, str] = {}

        logger.info("WebSocket ConnectionManager initialized")

    async def connect(self, websocket: WebSocket, user_id: str, username: Optional[str] = None) -> None:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: WebSocket connection
            user_id: User's unique ID
        """
        await websocket.accept()

        # Add to active connections
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

        # Map websocket to user
        self.websocket_to_user[websocket] = user_id

        # Update presence
        previous_presence = self.presence.get(user_id, {})
        self.presence[user_id] = {
            "status": "online",
            "last_seen": datetime.utcnow().isoformat(),
            "connected_at": datetime.utcnow().isoformat(),
            "username": username or previous_presence.get("username"),
            "location": previous_presence.get("location"),
        }

        logger.info(f"User {user_id} connected (total connections: {len(self.active_connections[user_id])})")

        # Broadcast presence update to all rooms user is in
        await self._broadcast_presence_update(user_id, "online")

    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection and cleanup.

        Args:
            websocket: WebSocket connection to remove
        """
        # Get user_id from websocket
        user_id = self.websocket_to_user.get(websocket)

        if not user_id:
            return

        # Remove from active connections
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)

            # If no more connections for this user, mark offline
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

                # Update presence
                if user_id in self.presence:
                    self.presence[user_id]["status"] = "offline"
                    self.presence[user_id]["last_seen"] = datetime.utcnow().isoformat()

                # Broadcast offline status
                await self._broadcast_presence_update(user_id, "offline")

                logger.info(f"User {user_id} disconnected (offline)")
            else:
                logger.info(f"User {user_id} connection closed (still has {len(self.active_connections[user_id])} active)")

        # Remove websocket mapping
        if websocket in self.websocket_to_user:
            del self.websocket_to_user[websocket]

    async def send_personal_message(self, message: dict, user_id: str) -> bool:
        """
        Send a message to a specific user (all their connections).

        Args:
            message: Message data dictionary
            user_id: Target user ID

        Returns:
            bool: True if message was sent, False if user not connected
        """
        if user_id not in self.active_connections:
            return False

        message_json = json.dumps(message)

        # Send to all user's connections
        disconnected = set()
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.error(f"Failed to send to user {user_id}: {e}")
                disconnected.add(websocket)

        # Clean up failed connections
        for ws in disconnected:
            await self.disconnect(ws)

        return True

    async def broadcast_to_room(self, message: dict, room_id: str, exclude_user: Optional[str] = None) -> int:
        """
        Broadcast a message to all users in a room.

        Args:
            message: Message data dictionary
            room_id: Room ID to broadcast to
            exclude_user: Optional user ID to exclude from broadcast

        Returns:
            int: Number of users message was sent to
        """
        if room_id not in self.rooms:
            return 0

        message_json = json.dumps(message)
        sent_count = 0

        for user_id in self.rooms[room_id]:
            # Skip excluded user
            if exclude_user and user_id == exclude_user:
                continue

            # Skip if user not connected
            if user_id not in self.active_connections:
                continue

            # Send to all user's connections
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_text(message_json)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to broadcast to user {user_id}: {e}")

        return sent_count

    async def broadcast_all(self, message: dict, exclude_user: Optional[str] = None) -> int:
        """
        Broadcast a message to every connected user.

        Args:
            message: Message data dictionary
            exclude_user: Optional user ID to skip

        Returns:
            int: Number of websocket sends attempted
        """
        if not self.active_connections:
            return 0

        message_json = json.dumps(message)
        sent_count = 0

        for user_id, sockets in self.active_connections.items():
            if exclude_user and user_id == exclude_user:
                continue

            for websocket in list(sockets):
                try:
                    await websocket.send_text(message_json)
                    sent_count += 1
                except Exception as exc:
                    logger.error(f"Failed to broadcast message to {user_id}: {exc}")
                    await self.disconnect(websocket)

        return sent_count

    async def join_room(self, user_id: str, room_id: str) -> bool:
        """
        Add user to a room.

        Args:
            user_id: User ID
            room_id: Room ID

        Returns:
            bool: True if joined successfully
        """
        if room_id not in self.rooms:
            self.rooms[room_id] = set()

        self.rooms[room_id].add(user_id)

        logger.info(f"User {user_id} joined room {room_id} ({len(self.rooms[room_id])} users)")

        # Notify room members
        await self.broadcast_to_room(
            {
                "type": "user_joined",
                "room_id": room_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            room_id,
            exclude_user=user_id
        )

        return True

    async def leave_room(self, user_id: str, room_id: str) -> bool:
        """
        Remove user from a room.

        Args:
            user_id: User ID
            room_id: Room ID

        Returns:
            bool: True if left successfully
        """
        if room_id not in self.rooms:
            return False

        self.rooms[room_id].discard(user_id)

        # Clean up empty rooms
        if not self.rooms[room_id]:
            del self.rooms[room_id]
            logger.info(f"Room {room_id} deleted (empty)")
        else:
            logger.info(f"User {user_id} left room {room_id} ({len(self.rooms[room_id])} users remaining)")

            # Notify room members
            await self.broadcast_to_room(
                {
                    "type": "user_left",
                    "room_id": room_id,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat()
                },
                room_id
            )

        return True

    async def update_user_location(self, user_id: str, x: int, y: int) -> None:
        """
        Update user's current location for proximity detection.

        Args:
            user_id: User ID
            x: X coordinate
            y: Y coordinate
        """
        if user_id in self.presence:
            self.presence[user_id]["location"] = {"x": x, "y": y}
            self.presence[user_id]["last_seen"] = datetime.utcnow().isoformat()

    def get_nearby_users(self, x: int, y: int, radius: int = 5) -> List[str]:
        """
        Get list of online users within radius of coordinates.

        Args:
            x: Center X coordinate
            y: Center Y coordinate
            radius: Search radius (default 5)

        Returns:
            List of user IDs within radius
        """
        nearby = []

        for user_id, presence_data in self.presence.items():
            # Skip offline users
            if presence_data.get("status") != "online":
                continue

            # Skip users without location
            location = presence_data.get("location")
            if not location:
                continue

            # Calculate distance (Chebyshev distance for grid)
            distance = max(
                abs(location["x"] - x),
                abs(location["y"] - y)
            )

            if distance <= radius:
                nearby.append(user_id)

        return nearby

    def get_room_members(self, room_id: str) -> List[str]:
        """
        Get list of user IDs in a room.

        Args:
            room_id: Room ID

        Returns:
            List of user IDs
        """
        return list(self.rooms.get(room_id, set()))

    def get_user_presence(self, user_id: str) -> Optional[dict]:
        """
        Get user's presence information.

        Args:
            user_id: User ID

        Returns:
            Presence dict or None if not found
        """
        return self.presence.get(user_id)

    def get_all_online_users(self) -> List[str]:
        """
        Get list of all currently online user IDs.

        Returns:
            List of online user IDs
        """
        return [
            user_id for user_id, data in self.presence.items()
            if data.get("status") == "online"
        ]

    def has_active_connections(self, user_id: str) -> bool:
        """
        Check if a user currently has active WebSocket connections.
        """
        return bool(self.active_connections.get(user_id))

    async def force_logout_user(self, user_id: str, reason: str = "session_terminated") -> bool:
        """
        Send a session invalidation event to all active connections for a user and disconnect them.

        Args:
            user_id: Target user ID
            reason: Human-readable reason for the logout
        """
        sockets = list(self.active_connections.get(user_id, []))
        if not sockets:
            return False

        message = json.dumps({
            "type": "session_invalidated",
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })

        for websocket in sockets:
            try:
                await websocket.send_text(message)
            except Exception as exc:
                logger.error(f"Failed to notify user {user_id} about session invalidation: {exc}")
            finally:
                try:
                    await self.disconnect(websocket)
                except Exception as disconnect_error:
                    logger.error(f"Failed to disconnect websocket for user {user_id}: {disconnect_error}")



    def get_stats(self) -> dict:
        """
        Get connection statistics.

        Returns:
            Statistics dictionary
        """
        total_connections = sum(len(conns) for conns in self.active_connections.values())

        return {
            "total_users_connected": len(self.active_connections),
            "total_connections": total_connections,
            "total_rooms": len(self.rooms),
            "online_users": len(self.get_all_online_users())
        }

    async def _broadcast_presence_update(self, user_id: str, status: str) -> None:
        """
        Broadcast presence update to all rooms user is in.

        Args:
            user_id: User ID
            status: New status (online/offline)
        """
        # Find all rooms this user is in
        user_rooms = [
            room_id for room_id, members in self.rooms.items()
            if user_id in members
        ]

        # Broadcast to each room
        message = {
            "type": "presence_update",
            "user_id": user_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }

        for room_id in user_rooms:
            await self.broadcast_to_room(message, room_id, exclude_user=user_id)


class MarketDataSubscriptionManager:
    """
    Manages WebSocket subscriptions to market data feeds.
    
    Channels:
    - quote:{instrument_id} - Top of book quotes
    - depth:{instrument_id} - Order book depth
    - trades:{instrument_id} - Recent trades
    - candles:{instrument_id}:{timeframe} - OHLCV candles
    - status:{instrument_id} - Instrument status changes
    """
    
    def __init__(self):
        # Subscriptions: {channel: Set[websocket]}
        self.subscriptions: Dict[str, Set[WebSocket]] = {}
        # Reverse mapping: {websocket: Set[channel]}
        self.websocket_channels: Dict[WebSocket, Set[str]] = {}
        
        logger.info("MarketDataSubscriptionManager initialized")
    
    async def subscribe(self, websocket: WebSocket, channel: str) -> None:
        """Subscribe a websocket to a market data channel."""
        if channel not in self.subscriptions:
            self.subscriptions[channel] = set()
        
        self.subscriptions[channel].add(websocket)
        
        if websocket not in self.websocket_channels:
            self.websocket_channels[websocket] = set()
        
        self.websocket_channels[websocket].add(channel)
        logger.info(f"WebSocket subscribed to {channel}")
    
    async def unsubscribe(self, websocket: WebSocket, channel: Optional[str] = None) -> None:
        """Unsubscribe from a channel (or all if channel is None)."""
        if channel:
            # Unsubscribe from specific channel
            if channel in self.subscriptions:
                self.subscriptions[channel].discard(websocket)
            
            if websocket in self.websocket_channels:
                self.websocket_channels[websocket].discard(channel)
            
            logger.info(f"WebSocket unsubscribed from {channel}")
        else:
            # Unsubscribe from all channels
            if websocket in self.websocket_channels:
                for ch in list(self.websocket_channels[websocket]):
                    if ch in self.subscriptions:
                        self.subscriptions[ch].discard(websocket)
                del self.websocket_channels[websocket]
            
            logger.info(f"WebSocket unsubscribed from all channels")
    
    async def publish(self, channel: str, data: dict) -> int:
        """
        Publish data to all subscribers of a channel.
        
        Args:
            channel: Channel name
            data: Data to publish
            
        Returns:
            Number of messages sent
        """
        if channel not in self.subscriptions or not self.subscriptions[channel]:
            return 0
        
        message = {
            "type": "market_data",
            "channel": channel,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        message_json = json.dumps(message)
        
        sent_count = 0
        disconnected = set()
        
        for websocket in self.subscriptions[channel]:
            try:
                await websocket.send_text(message_json)
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to publish to {channel}: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected websockets
        for ws in disconnected:
            await self.unsubscribe(ws)
        
        return sent_count
    
    def get_subscriber_count(self, channel: str) -> int:
        """Get number of subscribers to a channel."""
        return len(self.subscriptions.get(channel, set()))
    
    def get_subscriptions(self, websocket: WebSocket) -> Set[str]:
        """Get all subscriptions for a websocket."""
        return self.websocket_channels.get(websocket, set())


# Global connection manager instance
connection_manager = ConnectionManager()

# Global market data subscription manager
market_data_manager = MarketDataSubscriptionManager()
