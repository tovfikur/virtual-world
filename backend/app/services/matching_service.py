"""
Advanced matching service with iceberg disclosure, OCO linkage, trailing/stop activation,
and stricter IOC/FOK handling (still a scaffold, no persistence of filled quantity).
"""
from uuid import UUID
from decimal import Decimal
from typing import Dict, List, Tuple, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.order_book import OrderBook
from app.schemas.order_schema import OrderCreate, OrderSide, OrderType
from app.models.instrument import InstrumentStatus, Instrument
from app.models.order import Order, OrderStatus
from app.models.trade import Trade
from app.services.risk_service import risk_service
from app.models.market_status import MarketStatus, MarketState


class MatchingService:
    def __init__(self) -> None:
        self.books: Dict[UUID, OrderBook] = {}
        self.stop_orders: Dict[UUID, List[dict]] = {}  # per instrument stop/trailing
        self.iceberg_reserve: Dict[UUID, dict] = {}  # order_id -> remaining hidden, slice, user_id, price, side, client_order_id
        self.last_trade_price: Dict[UUID, Decimal] = {}
        self.oco_groups: Dict[str, List[UUID]] = {}

    def _tif_value(self, order: Order) -> str:
        val = getattr(order.time_in_force, "value", order.time_in_force)
        return str(val).lower()

    async def _get_instrument(self, db: AsyncSession, instrument_id: UUID) -> Instrument:
        result = await db.execute(select(Instrument).where(Instrument.instrument_id == instrument_id))
        inst = result.scalar_one_or_none()
        if not inst:
            raise ValueError("Instrument not found")
        if inst.status != InstrumentStatus.ACTIVE:
            raise ValueError("Instrument not active")
        return inst

    async def _ensure_market_open(self, db: AsyncSession) -> None:
        result = await db.execute(select(MarketStatus))
        row = result.scalar_one_or_none()
        if not row:
            row = MarketStatus(state=MarketState.OPEN.value)
            db.add(row)
            await db.commit()
            return
        if row.state != MarketState.OPEN:
            raise ValueError(f"Market is {row.state}: {row.reason or 'halted'}")

    def _register_oco(self, order: Order) -> None:
        if not order.oco_group_id:
            return
        group = self.oco_groups.setdefault(order.oco_group_id, [])
        if order.order_id not in group:
            group.append(order.order_id)

    def _register_stop(self, order: Order, payload: OrderCreate, book: OrderBook) -> None:
        entry = {
            "order_id": order.order_id,
            "side": order.side,
            "order_type": order.order_type,
            "limit_price": Decimal(payload.price) if payload.price is not None else None,
            "stop_price": Decimal(payload.stop_price) if payload.stop_price is not None else None,
            "trailing_offset": Decimal(payload.trailing_offset) if payload.trailing_offset is not None else None,
            "anchor": None,
        }
        # Seed anchor for trailing stop
        if order.order_type == OrderType.TRAILING_STOP:
            best_bid = max(book.bids.keys()) if book.bids else None
            best_ask = min(book.asks.keys()) if book.asks else None
            if order.side == OrderSide.SELL:
                entry["anchor"] = best_bid if best_bid is not None else entry["stop_price"] or Decimal("0")
            else:
                entry["anchor"] = best_ask if best_ask is not None else entry["stop_price"] or Decimal("0")

        self.stop_orders.setdefault(order.instrument_id, []).append(entry)

    def _remove_stop_entry(self, instrument_id: UUID, order_id: UUID) -> None:
        if instrument_id not in self.stop_orders:
            return
        self.stop_orders[instrument_id] = [
            e for e in self.stop_orders[instrument_id] if e["order_id"] != order_id
        ]

    def _has_sufficient_liquidity(self, book: OrderBook, side: OrderSide, qty: Decimal, price_limit: Optional[Decimal]) -> bool:
        remaining = qty
        levels = book.asks if side == OrderSide.BUY else book.bids
        prices = sorted(levels.keys()) if side == OrderSide.BUY else sorted(levels.keys(), reverse=True)
        for p in prices:
            if price_limit is not None:
                if side == OrderSide.BUY and p > price_limit:
                    break
                if side == OrderSide.SELL and p < price_limit:
                    break
            level_qty = sum(entry.quantity for entry in levels[p])
            remaining -= level_qty
            if remaining <= 0:
                return True
        return remaining <= 0

    async def place_order(
        self,
        db: AsyncSession,
        user_id: UUID,
        payload: OrderCreate,
    ) -> Order:
        inst = await self._get_instrument(db, payload.instrument_id)
        await self._ensure_market_open(db)
        risk_service.validate_order(inst, payload)

        effective_type = payload.order_type
        if effective_type == OrderType.OCO and payload.price is not None:
            effective_type = OrderType.LIMIT

        # Basic validation for stop/limit pricing
        if effective_type in {OrderType.LIMIT, OrderType.STOP_LIMIT} and payload.price is None:
            raise ValueError("Limit/stop-limit orders require price")
        if effective_type in {OrderType.STOP, OrderType.STOP_LIMIT} and payload.stop_price is None:
            raise ValueError("Stop/stop-limit orders require stop_price")
        if effective_type == OrderType.ICEBERG and not payload.iceberg_visible:
            raise ValueError("Iceberg orders require visible size")
        if effective_type == OrderType.TRAILING_STOP and not payload.trailing_offset:
            raise ValueError("Trailing stop requires trailing_offset")
        if payload.iceberg_visible and Decimal(payload.iceberg_visible) > Decimal(payload.quantity):
            raise ValueError("iceberg_visible cannot exceed total quantity")

        # Persist order record
        order = Order(
            instrument_id=payload.instrument_id,
            user_id=user_id,
            side=payload.side,
            order_type=effective_type,
            quantity=payload.quantity,
            price=payload.price,
            stop_price=payload.stop_price,
            trailing_offset=payload.trailing_offset,
            iceberg_visible=payload.iceberg_visible,
            oco_group_id=payload.oco_group_id,
            time_in_force=payload.time_in_force,
            client_order_id=payload.client_order_id,
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)

        self._register_oco(order)

        book = self.books.setdefault(payload.instrument_id, OrderBook())
        trades: List[Trade] = []
        remaining_qty = Decimal(payload.quantity)

        # Stop and trailing-stop orders: store for later activation
        if effective_type in {OrderType.STOP, OrderType.STOP_LIMIT, OrderType.TRAILING_STOP}:
            self._register_stop(order, payload, book)
            order.status = OrderStatus.PENDING
            await db.commit()
            await db.refresh(order)
            return order

        # Active orders (market/limit/iceberg)
        trades, remaining_qty = await self._process_active_order(
            db=db,
            order=order,
            book=book,
            qty=remaining_qty,
        )

        await db.commit()
        await db.refresh(order)
        return order

    async def _process_active_order(
        self,
        db: AsyncSession,
        order: Order,
        book: OrderBook,
        qty: Decimal,
    ) -> Tuple[List[Trade], Decimal]:
        trades: List[Trade] = []
        remaining = qty

        # FOK liquidity pre-check
        tif = self._tif_value(order)
        price_limit = Decimal(order.price) if order.price is not None else None
        if tif == "fok":
            if order.order_type == OrderType.MARKET:
                if not self._has_sufficient_liquidity(book, order.side, qty, None):
                    order.status = OrderStatus.CANCELLED
                    return [], qty
            elif order.order_type in {OrderType.LIMIT, OrderType.ICEBERG}:
                if not self._has_sufficient_liquidity(book, order.side, qty, price_limit):
                    order.status = OrderStatus.CANCELLED
                    return [], qty

        if order.order_type == OrderType.MARKET:
            # Reject market orders if no liquidity on opposite side
            if order.side == OrderSide.BUY and not book.asks:
                raise ValueError("No ask liquidity for market buy")
            if order.side == OrderSide.SELL and not book.bids:
                raise ValueError("No bid liquidity for market sell")
            trades, remaining = self._match_market(db=db, book=book, incoming=order, qty=qty)

        elif order.order_type in {OrderType.LIMIT, OrderType.ICEBERG}:
            if order.price is None:
                raise ValueError("Limit price required")
            if order.iceberg_visible:
                trades, remaining = self._place_iceberg(db, book, order, price_limit, qty)
            else:
                trades, remaining = self._match_limit(
                    db=db,
                    book=book,
                    incoming=order,
                    price=Decimal(order.price),
                    qty=qty,
                )
                if remaining > 0 and tif not in {"ioc", "fok"}:
                    book.add_limit(
                        order.side,
                        Decimal(order.price),
                        remaining,
                        order.client_order_id,
                        user_id=order.user_id,
                        order_id=order.order_id,
                    )
                    order.status = OrderStatus.PENDING
                elif remaining > 0 and tif == "ioc":
                    order.status = OrderStatus.PARTIAL

        # Status updates and maker updates
        if trades:
            filled_qty = sum(Decimal(t.quantity) for t in trades if t.buy_order_id == order.order_id or t.sell_order_id == order.order_id)
            if filled_qty >= order.quantity:
                order.status = OrderStatus.FILLED
            else:
                order.status = OrderStatus.PARTIAL
            await self._update_makers(db, maker_fills=trades, taker_side=order.side)
            self.last_trade_price[order.instrument_id] = Decimal(trades[-1].price)
            await self._evaluate_stops(db, order.instrument_id, self.last_trade_price[order.instrument_id])
            # Cancel OCO siblings once any execution happens
            await self._cancel_oco_siblings(db, order)
        else:
            if tif == "fok":
                order.status = OrderStatus.CANCELLED
            elif tif == "ioc":
                order.status = OrderStatus.CANCELLED if remaining == order.quantity else OrderStatus.PARTIAL

        return trades, remaining

    async def _cancel_oco_siblings(self, db: AsyncSession, order: Order) -> None:
        if not order.oco_group_id:
            return
        group = self.oco_groups.get(order.oco_group_id, [])
        siblings = [oid for oid in group if oid != order.order_id]
        if not siblings:
            return
        result = await db.execute(select(Order).where(Order.order_id.in_(siblings)))
        for sib in result.scalars().all():
            if sib.status in {OrderStatus.FILLED, OrderStatus.CANCELLED}:
                continue
            # Remove from order book and stop pool
            book = self.books.get(sib.instrument_id)
            if book:
                book.cancel(sib.order_id)
            self._remove_stop_entry(sib.instrument_id, sib.order_id)
            self.iceberg_reserve.pop(sib.order_id, None)
            sib.status = OrderStatus.CANCELLED
        # Clear group mapping
        self.oco_groups.pop(order.oco_group_id, None)

    async def _update_makers(self, db: AsyncSession, maker_fills: List[Trade], taker_side: OrderSide) -> None:
        maker_ids = {t.sell_order_id if taker_side == OrderSide.BUY else t.buy_order_id for t in maker_fills}
        if not maker_ids:
            return
        result = await db.execute(select(Order).where(Order.order_id.in_(maker_ids)))
        for maker in result.scalars().all():
            still_open = False
            book = self.books.get(maker.instrument_id)
            if book:
                levels = book.bids if maker.side == OrderSide.BUY else book.asks
                for q in levels.values():
                    if any(e.order_id == maker.order_id for e in q):
                        still_open = True
                        break
            maker.status = OrderStatus.PARTIAL if still_open else OrderStatus.FILLED
            if maker.status == OrderStatus.FILLED and maker.oco_group_id:
                await self._cancel_oco_siblings(db, maker)

    def _cross(self, taker_side: OrderSide, book: OrderBook, qty: Decimal, price_limit: Optional[Decimal]) -> Tuple[List[Tuple[UUID, UUID, Decimal, Decimal, Decimal, Optional[str]]], Decimal]:
        """
        Returns list of (maker_order_id, maker_user_id, price, qty_fill, maker_remaining_after, client_order_id) and remaining_qty.
        """
        fills: List[Tuple[UUID, UUID, Decimal, Decimal, Decimal, Optional[str]]] = []
        remaining = qty
        levels = book.asks if taker_side == OrderSide.BUY else book.bids
        level_prices = sorted(levels.keys()) if taker_side == OrderSide.BUY else sorted(levels.keys(), reverse=True)
        for level_price in level_prices:
            if price_limit is not None:
                if taker_side == OrderSide.BUY and level_price > price_limit:
                    break
                if taker_side == OrderSide.SELL and level_price < price_limit:
                    break
            queue = levels[level_price]
            while queue and remaining > 0:
                maker = queue[0]
                fill_qty = min(remaining, maker.quantity)
                remaining -= fill_qty
                maker.quantity -= fill_qty
                fills.append((maker.order_id, maker.user_id, level_price, fill_qty, maker.quantity, maker.client_order_id))
                if maker.quantity == 0:
                    queue.popleft()
            if not queue:
                levels.pop(level_price, None)
            if remaining <= 0:
                break
        return fills, remaining

    def _record_trades(self, db: AsyncSession, incoming: Order, maker_fills: List[Tuple[UUID, UUID, Decimal, Decimal, Decimal, Optional[str]]], taker_side: OrderSide) -> List[Trade]:
        trades: List[Trade] = []
        for maker_order_id, maker_user_id, price, qty, _remaining_after, _client_order_id in maker_fills:
            trade = Trade(
                buy_order_id=incoming.order_id if taker_side == OrderSide.BUY else maker_order_id,
                sell_order_id=incoming.order_id if taker_side == OrderSide.SELL else maker_order_id,
                instrument_id=incoming.instrument_id,
                price=price,
                quantity=qty,
                buyer_id=incoming.user_id if taker_side == OrderSide.BUY else maker_user_id,
                seller_id=incoming.user_id if taker_side == OrderSide.SELL else maker_user_id,
            )
            db.add(trade)
            trades.append(trade)
        return trades

    def _replenish_iceberg_if_needed(self, book: OrderBook, maker_side: OrderSide, maker_order_id: UUID, price: Decimal, client_order_id: Optional[str], maker_user_id: UUID) -> None:
        state = self.iceberg_reserve.get(maker_order_id)
        if not state:
            return
        if state["remaining"] <= 0:
            self.iceberg_reserve.pop(maker_order_id, None)
            return
        slice_qty = min(state["slice"], state["remaining"])
        state["remaining"] -= slice_qty
        book.add_limit(
            maker_side,
            price,
            slice_qty,
            client_order_id=client_order_id or state.get("client_order_id"),
            user_id=maker_user_id,
            order_id=maker_order_id,
        )

    def _match_limit(
        self,
        db: AsyncSession,
        book: OrderBook,
        incoming: Order,
        price: Decimal,
        qty: Decimal,
    ) -> Tuple[List[Trade], Decimal]:
        maker_fills_all: List[Tuple[UUID, UUID, Decimal, Decimal, Decimal, Optional[str]]] = []
        remaining = qty
        while remaining > 0:
            maker_fills, remaining = self._cross(
                taker_side=incoming.side,
                book=book,
                qty=remaining,
                price_limit=price,
            )
            if not maker_fills:
                break
            maker_fills_all.extend(maker_fills)
            for maker_order_id, maker_user_id, level_price, _fill_qty, maker_remaining_after, client_order_id in maker_fills:
                if maker_remaining_after == 0:
                    maker_side = OrderSide.SELL if incoming.side == OrderSide.BUY else OrderSide.BUY
                    self._replenish_iceberg_if_needed(book, maker_side, maker_order_id, level_price, client_order_id, maker_user_id)
        trades = self._record_trades(db, incoming, maker_fills_all, incoming.side)
        return trades, remaining

    def _match_market(
        self,
        db: AsyncSession,
        book: OrderBook,
        incoming: Order,
        qty: Decimal,
    ) -> Tuple[List[Trade], Decimal]:
        maker_fills_all: List[Tuple[UUID, UUID, Decimal, Decimal, Decimal, Optional[str]]] = []
        remaining = qty
        while remaining > 0:
            maker_fills, remaining = self._cross(
                taker_side=incoming.side,
                book=book,
                qty=remaining,
                price_limit=None,
            )
            if not maker_fills:
                break
            maker_fills_all.extend(maker_fills)
            for maker_order_id, maker_user_id, level_price, _fill_qty, maker_remaining_after, client_order_id in maker_fills:
                if maker_remaining_after == 0:
                    maker_side = OrderSide.SELL if incoming.side == OrderSide.BUY else OrderSide.BUY
                    self._replenish_iceberg_if_needed(book, maker_side, maker_order_id, level_price, client_order_id, maker_user_id)
        trades = self._record_trades(db, incoming, maker_fills_all, incoming.side)
        return trades, remaining

    def _place_iceberg(
        self,
        db: AsyncSession,
        book: OrderBook,
        order: Order,
        price: Decimal,
        total_qty: Decimal,
    ) -> Tuple[List[Trade], Decimal]:
        slice_qty = Decimal(order.iceberg_visible)
        visible = min(slice_qty, total_qty)
        remaining_hidden = total_qty - visible

        # First disclosed slice attempts to cross
        trades, remaining_visible = self._match_limit(db, book, order, price, visible)

        # If any remainder from first slice, rest it on book if allowed
        tif = self._tif_value(order)
        if remaining_visible > 0 and tif not in {"ioc", "fok"}:
            book.add_limit(
                order.side,
                price,
                remaining_visible,
                order.client_order_id,
                user_id=order.user_id,
                order_id=order.order_id,
            )
            visible_rest = remaining_visible
        else:
            visible_rest = Decimal("0")

        # If the disclosed slice fully filled and hidden remains, post a new slice
        if remaining_visible == 0 and remaining_hidden > 0 and tif not in {"ioc", "fok"}:
            next_slice = min(slice_qty, remaining_hidden)
            book.add_limit(
                order.side,
                price,
                next_slice,
                order.client_order_id,
                user_id=order.user_id,
                order_id=order.order_id,
            )
            remaining_hidden -= next_slice
            visible_rest = next_slice

        # Track hidden reserve for future replenishment
        self.iceberg_reserve[order.order_id] = {
            "remaining": remaining_hidden,
            "slice": slice_qty,
            "user_id": order.user_id,
            "client_order_id": order.client_order_id,
        }

        # Remaining qty for the order is the sum of hidden and posted visible rest (booked)
        remaining_total = remaining_hidden + visible_rest
        if trades and remaining_total > 0:
            order.status = OrderStatus.PARTIAL
        return trades, remaining_total

    async def _evaluate_stops(self, db: AsyncSession, instrument_id: UUID, last_price: Decimal) -> None:
        entries = self.stop_orders.get(instrument_id, [])
        if not entries:
            return
        still_pending: List[dict] = []
        for entry in entries:
            triggered = False
            if entry["order_type"] in {OrderType.STOP, OrderType.STOP_LIMIT}:
                if entry["side"] == OrderSide.BUY and last_price >= entry["stop_price"]:
                    triggered = True
                if entry["side"] == OrderSide.SELL and last_price <= entry["stop_price"]:
                    triggered = True
            elif entry["order_type"] == OrderType.TRAILING_STOP:
                if entry["side"] == OrderSide.SELL:
                    entry["anchor"] = max(entry["anchor"], last_price) if entry["anchor"] is not None else last_price
                    trigger = entry["anchor"] - entry["trailing_offset"]
                    if last_price <= trigger:
                        triggered = True
                else:
                    entry["anchor"] = min(entry["anchor"], last_price) if entry["anchor"] is not None else last_price
                    trigger = entry["anchor"] + entry["trailing_offset"]
                    if last_price >= trigger:
                        triggered = True

            if triggered:
                await self._activate_stop_entry(db, instrument_id, entry, last_price)
            else:
                still_pending.append(entry)

        self.stop_orders[instrument_id] = still_pending

    async def _activate_stop_entry(self, db: AsyncSession, instrument_id: UUID, entry: dict, last_price: Decimal) -> None:
        result = await db.execute(select(Order).where(Order.order_id == entry["order_id"]))
        order = result.scalar_one_or_none()
        if not order:
            return
        # Convert stop to active type
        if entry["order_type"] == OrderType.STOP:
            order.order_type = OrderType.MARKET
        elif entry["order_type"] == OrderType.STOP_LIMIT:
            order.order_type = OrderType.LIMIT
            order.price = entry["limit_price"]
        elif entry["order_type"] == OrderType.TRAILING_STOP:
            order.order_type = OrderType.MARKET
        # Execute as active order
        book = self.books.setdefault(instrument_id, OrderBook())
        await self._process_active_order(
            db=db,
            order=order,
            book=book,
            qty=Decimal(order.quantity),
        )


matching_service = MatchingService()
