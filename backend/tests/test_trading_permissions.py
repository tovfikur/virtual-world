import os
import uuid

import pytest
import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
DEFAULT_HEADERS = {"Content-Type": "application/json"}


def register_trader() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    email = f"trader_{suffix}@example.com"
    password = "UserPass123!"
    response = requests.post(
        f"{API_BASE_URL}/auth/register",
        json={
            "username": f"trader{suffix}",
            "email": email,
            "password": password,
        },
        headers=DEFAULT_HEADERS,
        timeout=10,
    )
    assert response.status_code == 201
    return email, password


def login_token(email: str, password: str) -> str:
    response = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": email, "password": password},
        headers=DEFAULT_HEADERS,
        timeout=10,
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def get_admin_token() -> str:
    response = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": "demo@example.com", "password": "DemoPassword123!"},
        headers=DEFAULT_HEADERS,
        timeout=10,
    )
    if response.status_code != 200:
        pytest.skip("Default admin user not available for trading tests")
    return response.json()["access_token"]


def test_non_admin_cannot_create_company():
    email, password = register_trader()
    token = login_token(email, password)

    payload = {
        "name": f"TestCo-{uuid.uuid4().hex[:6]}",
        "total_shares": 1000,
        "initial_price": 1,
    }

    response = requests.post(
        f"{API_BASE_URL}/trading/companies",
        json=payload,
        headers={"Authorization": f"Bearer {token}", **DEFAULT_HEADERS},
        timeout=10,
    )
    assert response.status_code == 403


def test_admin_can_create_company():
    token = get_admin_token()

    payload = {
        "name": f"AdminCo-{uuid.uuid4().hex[:6]}",
        "total_shares": 1500,
        "initial_price": 1,
    }

    response = requests.post(
        f"{API_BASE_URL}/trading/companies",
        json=payload,
        headers={"Authorization": f"Bearer {token}", **DEFAULT_HEADERS},
        timeout=10,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["total_shares"] == payload["total_shares"]


def test_buy_requires_balance_or_gateway():
    admin_token = get_admin_token()

    # Create a fresh company with a price that requires funds
    company_payload = {
        "name": f"CashCo-{uuid.uuid4().hex[:6]}",
        "total_shares": 1000,
        "initial_price": 10,
    }
    company_resp = requests.post(
        f"{API_BASE_URL}/trading/companies",
        json=company_payload,
        headers={"Authorization": f"Bearer {admin_token}", **DEFAULT_HEADERS},
        timeout=10,
    )
    assert company_resp.status_code == 201
    company_id = company_resp.json()["company_id"]

    # Register a normal user (balance defaults to 0)
    email, password = register_trader()
    user_token = login_token(email, password)

    # Attempt to buy without funds should return 402 and a payment URL
    tx_payload = {
        "company_id": company_id,
        "shares": 1,
        "fee_percent": 0,
        "fee_fixed_shares": 0,
    }
    tx_resp = requests.post(
        f"{API_BASE_URL}/trading/transactions",
        json=tx_payload,
        headers={"Authorization": f"Bearer {user_token}", **DEFAULT_HEADERS},
        timeout=10,
    )

    assert tx_resp.status_code == 402
    detail = tx_resp.json().get("detail")
    assert detail and detail.get("payment_required") is True
    assert detail.get("payment_url")
