import os
import uuid

import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")


def login_admin() -> str:
    resp = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": "demo@example.com", "password": "DemoPassword123!"},
        timeout=10,
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_create_and_list_instrument():
    token = login_admin()
    symbol = f"TST{uuid.uuid4().hex[:4]}".upper()
    payload = {
        "symbol": symbol,
        "name": "Test Instrument",
        "asset_class": "equity",
        "tick_size": "0.01",
        "lot_size": "1",
        "leverage_max": "1",
        "is_margin_allowed": False,
        "is_short_selling_allowed": False,
        "status": "active",
    }
    create_resp = requests.post(
        f"{API_BASE_URL}/instruments",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert create_resp.status_code == 201
    list_resp = requests.get(f"{API_BASE_URL}/instruments", timeout=10)
    assert list_resp.status_code == 200
    symbols = [inst["symbol"] for inst in list_resp.json()]
    assert symbol in symbols
