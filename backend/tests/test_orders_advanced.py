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
        "name": "Adv Test",
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


def test_oco_cancels_sibling():
    token = login_admin()
    instrument_id = ensure_instrument(token)

    group = f"oco-{uuid.uuid4()}"

    # Two sibling asks in one OCO group
    ask1 = requests.post(
        f"{API_BASE_URL}/orders",
        json={
            "instrument_id": instrument_id,
            "side": "sell",
            "order_type": "limit",
            "quantity": "1",
            "price": "10",
            "time_in_force": "gtc",
            "oco_group_id": group,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert ask1.status_code == 201
    ask2 = requests.post(
        f"{API_BASE_URL}/orders",
        json={
            "instrument_id": instrument_id,
            "side": "sell",
            "order_type": "limit",
            "quantity": "1",
            "price": "11",
            "time_in_force": "gtc",
            "oco_group_id": group,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert ask2.status_code == 201

    # Market buy hits best ask and should cancel sibling
    buy_resp = requests.post(
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
    assert buy_resp.status_code == 201

    list_resp = requests.get(
        f"{API_BASE_URL}/orders",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    statuses = {o["order_id"]: o["status"] for o in list_resp.json()}
    assert statuses[ask1.json()["order_id"]] in {"filled", "partial"}
    assert statuses[ask2.json()["order_id"]] == "cancelled"


def test_iceberg_replenishes_and_fills():
    token = login_admin()
    instrument_id = ensure_instrument(token)

    iceberg = requests.post(
        f"{API_BASE_URL}/orders",
        json={
            "instrument_id": instrument_id,
            "side": "sell",
            "order_type": "iceberg",
            "quantity": "5",
            "price": "10",
            "iceberg_visible": "2",
            "time_in_force": "gtc",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert iceberg.status_code == 201

    # First taker consumes more than visible slice; replenishment should serve next slice
    buy1 = requests.post(
        f"{API_BASE_URL}/orders",
        json={
            "instrument_id": instrument_id,
            "side": "buy",
            "order_type": "market",
            "quantity": "3",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert buy1.status_code == 201

    # Second taker should clear the rest
    buy2 = requests.post(
        f"{API_BASE_URL}/orders",
        json={
            "instrument_id": instrument_id,
            "side": "buy",
            "order_type": "market",
            "quantity": "2",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert buy2.status_code == 201

    orders = requests.get(
        f"{API_BASE_URL}/orders",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    ).json()
    ice_status = next(o["status"] for o in orders if o["order_id"] == iceberg.json()["order_id"])
    assert ice_status == "filled"


def test_fok_rejects_partial_fill():
    token = login_admin()
    instrument_id = ensure_instrument(token)

    # Only 1 share resting
    resting = requests.post(
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
    assert resting.status_code == 201

    # FOK buy for 2 shares should cancel (no partial fills)
    fok_buy = requests.post(
        f"{API_BASE_URL}/orders",
        json={
            "instrument_id": instrument_id,
            "side": "buy",
            "order_type": "limit",
            "quantity": "2",
            "price": "10",
            "time_in_force": "fok",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert fok_buy.status_code == 201
    assert fok_buy.json()["status"] == "cancelled"
