"""
Password Policy Tests (HTTP)
Covers registration validation by calling the running backend API.
Skips tests if the backend is not reachable.
"""

import os
import requests
import pytest
from uuid import uuid4

API_URL = os.environ.get("API_URL", "http://localhost:8000/api/v1")


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid4().hex[:8]}@example.com"


def register(username: str, email: str, password: str):
    # Ensure unique, alphanumeric username per run to avoid conflicts
    unique_username = f"{username}{uuid4().hex[:6]}"
    return requests.post(
        f"{API_URL}/auth/register",
        json={
            "username": unique_username,
            "email": email,
            "password": password,
        },
        timeout=30,
    )


def backend_available() -> bool:
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not backend_available(), reason="Backend not reachable")
def test_password_too_short():
    resp = register("shorty", unique_email("short"), "Short1!")  # len 7
    assert resp.status_code in [400, 422]


@pytest.mark.skipif(not backend_available(), reason="Backend not reachable")
def test_password_missing_uppercase():
    resp = register("noupcase", unique_email("noups"), "lowercase123!")
    assert resp.status_code in [400, 422]


@pytest.mark.skipif(not backend_available(), reason="Backend not reachable")
def test_password_missing_lowercase():
    resp = register("nolow", unique_email("nolow"), "UPPERCASE123!")
    assert resp.status_code in [400, 422]


@pytest.mark.skipif(not backend_available(), reason="Backend not reachable")
def test_password_missing_number():
    resp = register("nonum", unique_email("nonum"), "NoNumbers!!Aa")
    assert resp.status_code in [400, 422]


@pytest.mark.skipif(not backend_available(), reason="Backend not reachable")
def test_password_missing_special():
    resp = register("nospec", unique_email("nospec"), "NoSpecial123Aa")
    assert resp.status_code in [400, 422]


@pytest.mark.skipif(not backend_available(), reason="Backend not reachable")
def test_password_min_length_exact_ok():
    # Exactly 12 chars: A a 1 ! + 8 a's => 12
    strong = "Aa1!aaaaaaaa"
    assert len(strong) == 12
    resp = register("exact12", unique_email("exact12"), strong)
    assert resp.status_code in [200, 201]


@pytest.mark.skipif(not backend_available(), reason="Backend not reachable")
def test_password_strong_common_case_ok():
    resp = register("stronguser", unique_email("strong"), "StrongPass123!")
    assert resp.status_code in [200, 201]
