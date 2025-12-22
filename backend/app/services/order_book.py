"""
In-memory order book scaffold (price-time priority).
Not yet persisted; intended as a step toward the full matching engine.
"""
from collections import deque
from decimal import Decimal
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional
from uuid import UUID, uuid4

from app.schemas.order_schema import OrderSide, OrderType, OrderBookLevel, TopOfBook


@dataclass
class OrderEntry:
    order_id: UUID
    user_id: UUID
    side: OrderSide
    price: Optional[Decimal]
    quantity: Decimal
    client_order_id: Optional[str] = None


class OrderBook:
    """
    Simple in-memory book with price-time priority for one instrument.
    """

    def __init__(self) -> None:
        self.bids: Dict[Decimal, Deque[OrderEntry]] = {}
        self.asks: Dict[Decimal, Deque[OrderEntry]] = {}

    def _levels(self, side: OrderSide) -> Dict[Decimal, Deque[OrderEntry]]:
        return self.bids if side == OrderSide.BUY else self.asks

    def add_limit(
        self,
        side: OrderSide,
        price: Decimal,
        quantity: Decimal,
        client_order_id: Optional[str] = None,
        user_id: Optional[UUID] = None,
        order_id: Optional[UUID] = None,
    ) -> UUID:
        order_id = order_id or uuid4()
        levels = self._levels(side)
        queue = levels.setdefault(price, deque())
        queue.append(
            OrderEntry(
                order_id=order_id,
                user_id=user_id or uuid4(),
                side=side,
                price=price,
                quantity=quantity,
                client_order_id=client_order_id,
            )
        )
        return order_id

    def cancel(self, order_id: UUID) -> bool:
        for levels in (self.bids, self.asks):
            for price, queue in list(levels.items()):
                remaining = deque()
                found = False
                while queue:
                    entry = queue.popleft()
                    if entry.order_id == order_id:
                        found = True
                        continue
                    remaining.append(entry)
                if remaining:
                    levels[price] = remaining
                else:
                    del levels[price]
                if found:
                    return True
        return False

    def top_of_book(self) -> TopOfBook:
        best_bid = None
        if self.bids:
            best_bid_price = max(self.bids.keys())
            qty = sum(entry.quantity for entry in self.bids[best_bid_price])
            best_bid = OrderBookLevel(price=best_bid_price, quantity=qty, orders=len(self.bids[best_bid_price]))
        best_ask = None
        if self.asks:
            best_ask_price = min(self.asks.keys())
            qty = sum(entry.quantity for entry in self.asks[best_ask_price])
            best_ask = OrderBookLevel(price=best_ask_price, quantity=qty, orders=len(self.asks[best_ask_price]))
        return TopOfBook(best_bid=best_bid, best_ask=best_ask)

    def depth(self, depth: int = 10) -> Dict[str, List[OrderBookLevel]]:
        bids = sorted(self.bids.items(), key=lambda x: x[0], reverse=True)[:depth]
        asks = sorted(self.asks.items(), key=lambda x: x[0])[:depth]
        bid_levels = [
            OrderBookLevel(price=price, quantity=sum(e.quantity for e in queue), orders=len(queue))
            for price, queue in bids
        ]
        ask_levels = [
            OrderBookLevel(price=price, quantity=sum(e.quantity for e in queue), orders=len(queue))
            for price, queue in asks
        ]
        return {"bids": bid_levels, "asks": ask_levels}
