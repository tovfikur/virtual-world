import uuid

import requests

API_BASE_URL = "http://localhost:8000/api/v1"


def login_admin() -> str:
    resp = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": "demo@example.com", "password": "DemoPassword123!"},
        timeout=10,
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def ensure_instrument(token: str) -> str:
    symbol = f"TST{uuid.uuid4().hex[:4]}".upper()
    payload = {
        "symbol": symbol,
        "name": "Match Test",
        "asset_class": "equity",
        "tick_size": "0.01",
        "lot_size": "1",
        "leverage_max": "1",
        "is_margin_allowed": False,
        "is_short_selling_allowed": False,
        "status": "active",
    }
    resp = requests.post(
        f"{API_BASE_URL}/instruments",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert resp.status_code == 201
    return resp.json()["instrument_id"]


def test_limit_then_market_match():
    token = login_admin()
    instrument_id = ensure_instrument(token)

    # Place resting ask
    ask_resp = requests.post(
        f"{API_BASE_URL}/orders",
        json={
            "instrument_id": instrument_id,
            "side": "sell",
            "order_type": "limit",
            "quantity": "1",
            "price": "10",
            "time_in_force": "gtc",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert ask_resp.status_code == 201
    ask_order_id = ask_resp.json()["order_id"]

    # Market buy should match the resting ask
    buy_resp = requests.post(
        f"{API_BASE_URL}/orders",
        json={
            "instrument_id": instrument_id,
            "side": "buy",
            "order_type": "market",
            "quantity": "1",
            "time_in_force": "gtc",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert buy_resp.status_code == 201
    assert buy_resp.json()["status"] in {"filled", "partial"}

    # The resting ask should be filled or removed
    list_resp = requests.get(
        f"{API_BASE_URL}/orders",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert list_resp.status_code == 200
    statuses = {o["order_id"]: o["status"] for o in list_resp.json()}
    assert statuses.get(ask_order_id) in {"filled", "partial"}

    # Trades should be recorded
    trades_resp = requests.get(
        f"{API_BASE_URL}/trades",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert trades_resp.status_code == 200
    assert len(trades_resp.json()) >= 1
