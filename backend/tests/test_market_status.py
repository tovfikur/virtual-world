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
        "name": "Market Test",
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


def test_market_halt_blocks_orders():
    token = login_admin()
    instrument_id = ensure_instrument(token)

    # Halt market
    halt_resp = requests.post(
        f"{API_BASE_URL}/market/status",
        json={"state": "halted", "reason": "maintenance"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert halt_resp.status_code == 200
    assert halt_resp.json()["state"] == "halted"

    # Order should fail while halted
    order_resp = requests.post(
        f"{API_BASE_URL}/orders",
        json={
            "instrument_id": instrument_id,
            "side": "buy",
            "order_type": "market",
            "quantity": "1",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert order_resp.status_code == 400

    # Re-open and ensure order works
    open_resp = requests.post(
        f"{API_BASE_URL}/market/status",
        json={"state": "open"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert open_resp.status_code == 200

    # Add resting liquidity once open
    ask_resp = requests.post(
        f"{API_BASE_URL}/orders",
        json={
            "instrument_id": instrument_id,
            "side": "sell",
            "order_type": "limit",
            "quantity": "1",
            "price": "1",
            "time_in_force": "gtc",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert ask_resp.status_code == 201

    order_resp2 = requests.post(
        f"{API_BASE_URL}/orders",
        json={
            "instrument_id": instrument_id,
            "side": "buy",
            "order_type": "market",
            "quantity": "1",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert order_resp2.status_code == 201
