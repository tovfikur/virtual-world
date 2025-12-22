"""
Notification service for real-time market data and trading updates.
Implements subscription-based notification delivery with message batching and filtering.
"""

from typing import Dict, List, Optional, Set, Callable, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import asyncio
import json
import logging
from enum import Enum
from dataclasses import dataclass, asdict
from uuid import UUID

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications."""
    # Trading notifications
    ORDER_CREATED = "order.created"
    ORDER_FILLED = "order.filled"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_REJECTED = "order.rejected"
    TRADE_EXECUTED = "trade.executed"
    
    # Market data notifications
    PRICE_UPDATE = "price.update"
    DEPTH_UPDATE = "depth.update"
    TRADE_BROADCAST = "trade.broadcast"
    CANDLE_UPDATE = "candle.update"
    
    # Account notifications
    MARGIN_CALL = "margin.call"
    LIQUIDATION_ALERT = "liquidation.alert"
    POSITION_UPDATE = "position.update"
    BALANCE_UPDATE = "balance.update"
    
    # Admin notifications
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker.triggered"
    INSTRUMENT_HALTED = "instrument.halted"
    INSTRUMENT_RESUMED = "instrument.resumed"
    SURVEILLANCE_ALERT = "surveillance.alert"
    
    # System notifications
    SYSTEM_MAINTENANCE = "system.maintenance"
    CONNECTION_CLOSED = "connection.closed"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"           # Non-time-critical updates
    NORMAL = "normal"     # Standard updates
    HIGH = "high"         # Important updates
    CRITICAL = "critical" # Immediate delivery required


@dataclass
class Notification:
    """Notification message structure."""
    id: str
    type: NotificationType
    priority: NotificationPriority
    recipient_id: int  # User ID or broker ID
    data: Dict[str, Any]
    timestamp: datetime
    expires_at: Optional[datetime] = None
    
    def to_json(self) -> str:
        """Convert to JSON for transmission."""
        return json.dumps({
            "id": self.id,
            "type": self.type.value,
            "priority": self.priority.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        })


@dataclass
class Subscription:
    """Subscription to notification types."""
    user_id: int
    notification_types: Set[NotificationType]
    instruments: Optional[Set[UUID]] = None  # None = all instruments
    brokers: Optional[Set[str]] = None       # None = own broker only
    filter_fn: Optional[Callable] = None     # Custom filter function
    
    def matches(self, notification: Notification) -> bool:
        """Check if notification matches subscription."""
        # Check type
        if notification.type not in self.notification_types:
            return False
        
        # Check instruments if specified
        if self.instruments is not None:
            instrument_id = notification.data.get("instrument_id")
            if instrument_id and UUID(str(instrument_id)) not in self.instruments:
                return False
        
        # Check brokers if specified
        if self.brokers is not None:
            broker_id = notification.data.get("broker_id")
            if broker_id and broker_id not in self.brokers:
                return False
        
        # Apply custom filter
        if self.filter_fn and not self.filter_fn(notification):
            return False
        
        return True


class NotificationService:
    """
    Service for managing and delivering notifications.
    
    Features:
    - Subscription management with filtering
    - Message batching for efficiency
    - Priority-based delivery
    - Expiration handling
    - Dead letter queue for failed deliveries
    """
    
    def __init__(self, batch_size: int = 10, batch_timeout_ms: int = 100):
        """Initialize notification service."""
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        
        # Subscriptions: {user_id: Set[Subscription]}
        self.subscriptions: Dict[int, Set[Subscription]] = {}
        
        # Pending notifications: {user_id: List[Notification]}
        self.pending_notifications: Dict[int, List[Notification]] = {}
        
        # Dead letter queue for failed deliveries
        self.dead_letter_queue: List[Notification] = []
        
        # Batch tasks per user
        self.batch_tasks: Dict[int, asyncio.Task] = {}
        
        # Delivery callbacks: {user_id: Callable}
        self.delivery_callbacks: Dict[int, Callable] = {}
        
        logger.info("NotificationService initialized")
    
    def subscribe(
        self,
        user_id: int,
        notification_types: List[NotificationType],
        instruments: Optional[List[UUID]] = None,
        brokers: Optional[List[str]] = None,
        filter_fn: Optional[Callable] = None
    ) -> Subscription:
        """Create a subscription for a user."""
        subscription = Subscription(
            user_id=user_id,
            notification_types=set(notification_types),
            instruments=set(instruments) if instruments else None,
            brokers=set(brokers) if brokers else None,
            filter_fn=filter_fn
        )
        
        if user_id not in self.subscriptions:
            self.subscriptions[user_id] = set()
        
        self.subscriptions[user_id].add(subscription)
        
        logger.debug(f"User {user_id} subscribed to {len(notification_types)} types")
        
        return subscription
    
    def unsubscribe(self, user_id: int, subscription: Subscription) -> None:
        """Remove a subscription."""
        if user_id in self.subscriptions:
            self.subscriptions[user_id].discard(subscription)
            
            if not self.subscriptions[user_id]:
                del self.subscriptions[user_id]
            
            logger.debug(f"User {user_id} unsubscribed")
    
    def subscribe_to_instrument_updates(
        self,
        user_id: int,
        instruments: List[UUID]
    ) -> Subscription:
        """Subscribe user to price/depth/trade updates for specific instruments."""
        return self.subscribe(
            user_id,
            [
                NotificationType.PRICE_UPDATE,
                NotificationType.DEPTH_UPDATE,
                NotificationType.TRADE_BROADCAST,
                NotificationType.CANDLE_UPDATE
            ],
            instruments=instruments
        )
    
    def subscribe_to_trading_updates(self, user_id: int) -> Subscription:
        """Subscribe user to their own trading updates."""
        return self.subscribe(
            user_id,
            [
                NotificationType.ORDER_CREATED,
                NotificationType.ORDER_FILLED,
                NotificationType.ORDER_CANCELLED,
                NotificationType.ORDER_REJECTED,
                NotificationType.TRADE_EXECUTED,
                NotificationType.MARGIN_CALL,
                NotificationType.LIQUIDATION_ALERT,
                NotificationType.POSITION_UPDATE,
                NotificationType.BALANCE_UPDATE
            ]
        )
    
    def subscribe_to_market_data(self, user_id: int) -> Subscription:
        """Subscribe user to all market data updates."""
        return self.subscribe(
            user_id,
            [
                NotificationType.PRICE_UPDATE,
                NotificationType.DEPTH_UPDATE,
                NotificationType.TRADE_BROADCAST,
                NotificationType.CANDLE_UPDATE
            ]
        )
    
    async def publish(
        self,
        notification_type: NotificationType,
        recipient_ids: List[int],
        data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.NORMAL,
        expires_in_seconds: Optional[int] = None
    ) -> List[Notification]:
        """
        Publish a notification to multiple recipients.
        
        Args:
            notification_type: Type of notification
            recipient_ids: List of user IDs to notify
            data: Notification data
            priority: Priority level
            expires_in_seconds: Seconds until expiration
        
        Returns:
            List of created notifications
        """
        import uuid as uuid_lib
        from datetime import timedelta
        
        notifications = []
        now = datetime.utcnow()
        expires_at = None
        
        if expires_in_seconds:
            expires_at = now + timedelta(seconds=expires_in_seconds)
        
        for recipient_id in recipient_ids:
            notification = Notification(
                id=str(uuid_lib.uuid4()),
                type=notification_type,
                priority=priority,
                recipient_id=recipient_id,
                data=data,
                timestamp=now,
                expires_at=expires_at
            )
            
            # Check subscriptions
            if recipient_id in self.subscriptions:
                subscribed = any(
                    sub.matches(notification)
                    for sub in self.subscriptions[recipient_id]
                )
                
                if not subscribed:
                    continue
            
            # Add to pending queue
            if recipient_id not in self.pending_notifications:
                self.pending_notifications[recipient_id] = []
            
            self.pending_notifications[recipient_id].append(notification)
            notifications.append(notification)
            
            # Schedule batch delivery if not already scheduled
            if recipient_id not in self.batch_tasks or self.batch_tasks[recipient_id].done():
                self.batch_tasks[recipient_id] = asyncio.create_task(
                    self._deliver_batch(recipient_id)
                )
        
        logger.debug(f"Published {notification_type.value} to {len(notifications)} recipients")
        
        return notifications
    
    async def _deliver_batch(self, user_id: int, force: bool = False) -> None:
        """
        Batch and deliver pending notifications for a user.
        
        Args:
            user_id: User to deliver to
            force: Force immediate delivery
        """
        try:
            # Wait for batch timeout or batch size
            start_time = asyncio.get_event_loop().time()
            
            while True:
                # Check if batch is ready
                pending = self.pending_notifications.get(user_id, [])
                
                if len(pending) >= self.batch_size or force:
                    break
                
                # Check timeout
                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
                if elapsed >= self.batch_timeout_ms:
                    break
                
                # Wait a bit
                await asyncio.sleep(0.01)
            
            # Get pending notifications
            pending = self.pending_notifications.get(user_id, [])
            if not pending:
                return
            
            # Filter expired
            now = datetime.utcnow()
            valid = [n for n in pending if n.expires_at is None or n.expires_at > now]
            expired = [n for n in pending if n.expires_at is not None and n.expires_at <= now]
            
            # Sort by priority (critical first)
            priority_order = {
                NotificationPriority.CRITICAL: 0,
                NotificationPriority.HIGH: 1,
                NotificationPriority.NORMAL: 2,
                NotificationPriority.LOW: 3
            }
            valid.sort(key=lambda n: priority_order.get(n.priority, 999))
            
            # Deliver batch
            if valid:
                await self._deliver_notifications(user_id, valid)
            
            # Clear delivered
            self.pending_notifications[user_id] = []
            
            # Log expired
            if expired:
                logger.debug(f"Expired {len(expired)} notifications for user {user_id}")
                self.dead_letter_queue.extend(expired)
        
        except Exception as e:
            logger.error(f"Error delivering batch for user {user_id}: {e}")
    
    async def _deliver_notifications(
        self,
        user_id: int,
        notifications: List[Notification]
    ) -> None:
        """Deliver notifications to user via registered callback."""
        if user_id not in self.delivery_callbacks:
            # No callback registered, queue for later
            if user_id not in self.pending_notifications:
                self.pending_notifications[user_id] = []
            self.pending_notifications[user_id].extend(notifications)
            return
        
        try:
            callback = self.delivery_callbacks[user_id]
            await callback(notifications)
        except Exception as e:
            logger.error(f"Failed to deliver {len(notifications)} notifications to user {user_id}: {e}")
            # Move to dead letter queue
            self.dead_letter_queue.extend(notifications)
    
    def register_delivery_callback(self, user_id: int, callback: Callable) -> None:
        """Register a callback for receiving notifications."""
        self.delivery_callbacks[user_id] = callback
        logger.debug(f"Registered delivery callback for user {user_id}")
    
    def unregister_delivery_callback(self, user_id: int) -> None:
        """Unregister delivery callback."""
        if user_id in self.delivery_callbacks:
            del self.delivery_callbacks[user_id]
            logger.debug(f"Unregistered delivery callback for user {user_id}")
    
    async def get_pending(self, user_id: int, limit: int = 100) -> List[Notification]:
        """Get pending notifications for a user."""
        return self.pending_notifications.get(user_id, [])[:limit]
    
    async def clear_pending(self, user_id: int) -> int:
        """Clear all pending notifications for a user."""
        count = len(self.pending_notifications.get(user_id, []))
        if user_id in self.pending_notifications:
            del self.pending_notifications[user_id]
        return count
    
    def get_dead_letters(self, limit: int = 100) -> List[Notification]:
        """Get notifications from dead letter queue."""
        return self.dead_letter_queue[-limit:]
    
    def clear_dead_letters(self) -> int:
        """Clear dead letter queue."""
        count = len(self.dead_letter_queue)
        self.dead_letter_queue.clear()
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        total_pending = sum(len(n) for n in self.pending_notifications.values())
        
        return {
            "subscriptions": len(self.subscriptions),
            "subscribers": sum(len(subs) for subs in self.subscriptions.values()),
            "pending_notifications": total_pending,
            "dead_letter_queue_size": len(self.dead_letter_queue),
            "active_delivery_callbacks": len(self.delivery_callbacks),
            "active_batch_tasks": sum(1 for t in self.batch_tasks.values() if not t.done())
        }


# Global notification service instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get or create notification service."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
