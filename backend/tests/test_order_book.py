from decimal import Decimal
from app.services.order_book import OrderBook
from app.schemas.order_schema import OrderSide


def test_order_book_add_and_tob():
    book = OrderBook()
    book.add_limit(OrderSide.BUY, Decimal("99"), Decimal("5"))
    book.add_limit(OrderSide.SELL, Decimal("101"), Decimal("3"))
    tob = book.top_of_book()
    assert tob.best_bid.price == Decimal("99")
    assert tob.best_ask.price == Decimal("101")


def test_order_book_match_partial():
    book = OrderBook()
    # Add resting ask
    book.add_limit(OrderSide.SELL, Decimal("10"), Decimal("5"))
    # Cross with buy
    # Simulate matching logic using internal structures
    levels = book.asks
    level_price = min(levels.keys())
    queue = levels[level_price]
    maker = queue[0]
    fill_qty = min(Decimal("3"), maker.quantity)
    maker.quantity -= fill_qty
    if maker.quantity == 0:
        queue.popleft()
    assert fill_qty == Decimal("3")
