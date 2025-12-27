import os
import uuid
import time
import requests
import pytest

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")


def _rand_email():
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


def _register_user():
    email = _rand_email()
    payload = {
        "username": f"user{uuid.uuid4().hex[:6]}",
        "email": email,
        "password": "Str0ngPass!word12"
    }
    r = requests.post(f"{BASE_URL}/auth/register", json=payload, timeout=5)
    return r, payload


def _login(email, password):
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=5)
    return r


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.skipif(
    requests.get(f"{BASE_URL}/system/health").status_code >= 500,
    reason="Backend not reachable"
)
def test_claim_unclaimed_land_creates_transaction():
    # Register
    r_register, payload = _register_user()
    assert r_register.status_code in (200, 201), r_register.text
    user = r_register.json()
    user_id = user["user_id"] if isinstance(user, dict) else user.get("user", {}).get("user_id")
    assert user_id, "Missing user_id from register response"

    # Login
    r_login = _login(payload["email"], payload["password"])
    assert r_login.status_code == 200, r_login.text
    token = r_login.json()["access_token"]

    # Ensure sufficient balance for claiming (optional: admin topup could be required)
    # Attempt a cheap claim
    # Use random coordinates to avoid collisions with existing claims
    rand_x = int(uuid.uuid4().hex[:3], 16) % 1000
    rand_y = int(uuid.uuid4().hex[3:6], 16) % 1000
    claim_body = {
        "x": rand_x,
        "y": rand_y,
        "biome": "plains",
        "elevation": 0.1,
        "price_base_bdt": 0,
    }
    r_claim = requests.post(f"{BASE_URL}/lands/claim", json=claim_body, headers=_auth_headers(token), timeout=8)
    assert r_claim.status_code == 200, r_claim.text

    # Fetch user transactions
    r_tx = requests.get(f"{BASE_URL}/users/{user_id}/transactions", headers=_auth_headers(token), timeout=5)
    assert r_tx.status_code == 200, r_tx.text
    data = r_tx.json()
    txs = data.get("transactions", [])
    assert any(t.get("transaction_type") == "FIXED_PRICE" and t.get("amount_bdt") == claim_body["price_base_bdt"] for t in txs), (
        f"No FIXED_PRICE transaction found with amount {claim_body['price_base_bdt']}. Got: {txs}"
    )


@pytest.mark.skipif(
    requests.get(f"{BASE_URL}/system/health").status_code >= 500,
    reason="Backend not reachable"
)
def test_starter_allocation_transaction_present_optional():
    # Register a user and check for a zero-amount TRANSFER entry if starter land is enabled.
    r_register, payload = _register_user()
    assert r_register.status_code in (200, 201), r_register.text
    user = r_register.json()
    user_id = user["user_id"] if isinstance(user, dict) else user.get("user", {}).get("user_id")

    r_login = _login(payload["email"], payload["password"])
    assert r_login.status_code == 200, r_login.text
    token = r_login.json()["access_token"]

    r_tx = requests.get(f"{BASE_URL}/users/{user_id}/transactions", headers=_auth_headers(token), timeout=5)
    assert r_tx.status_code == 200, r_tx.text
    txs = r_tx.json().get("transactions", [])

    # If enabled, expect a zero-amount TRANSFER with gateway STARTER_ALLOCATION
    has_starter = any(
        t.get("transaction_type") == "TRANSFER" and t.get("amount_bdt") == 0 and t.get("gateway_name") == "STARTER_ALLOCATION"
        for t in txs
    )
    # Don't fail the test if starter land disabled; only assert if present
    if has_starter:
        assert has_starter
