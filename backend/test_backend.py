"""
Quick test script to verify backend is working
Run this after starting the server to test basic functionality
"""

import requests
import json

BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/v1"


def test_health():
    """Test health check endpoint."""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    print("✓ Health check passed\n")


def test_register():
    """Test user registration."""
    print("Testing user registration...")
    data = {
        "username": "testuser123",
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "country_code": "BD"
    }
    response = requests.post(f"{API_URL}/auth/register", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    if response.status_code == 201:
        print("✓ Registration successful\n")
        return response.json()
    elif response.status_code == 409:
        print("⚠ User already exists (expected if running multiple times)\n")
        return None
    else:
        print("✗ Registration failed\n")
        return None


def test_login():
    """Test user login."""
    print("Testing user login...")
    data = {
        "email": "test@example.com",
        "password": "SecurePassword123!"
    }
    response = requests.post(f"{API_URL}/auth/login", json=data)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"✓ Login successful")
        print(f"Access Token: {result['access_token'][:50]}...")
        print(f"User ID: {result['user']['user_id']}")
        print(f"Username: {result['user']['username']}\n")
        return result['access_token']
    else:
        print(f"✗ Login failed: {response.json()}\n")
        return None


def test_get_me(token):
    """Test getting current user info."""
    print("Testing /auth/me endpoint...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_URL}/auth/me", headers=headers)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        user = response.json()
        print(f"✓ Got user info")
        print(f"Username: {user['username']}")
        print(f"Email: {user['email']}")
        print(f"Balance: {user['balance_bdt']} BDT\n")
    else:
        print(f"✗ Failed to get user info\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Virtual Land World - Backend API Test")
    print("=" * 60 + "\n")

    try:
        # Test health
        test_health()

        # Test registration
        test_register()

        # Test login and get token
        token = test_login()

        if token:
            # Test authenticated endpoint
            test_get_me(token)

            print("=" * 60)
            print("✓ All tests passed!")
            print("=" * 60)
        else:
            print("⚠ Could not complete authenticated tests (login failed)")

    except requests.exceptions.ConnectionError:
        print("✗ Error: Could not connect to backend server")
        print("Make sure the server is running:")
        print("  cd backend")
        print("  uvicorn app.main:app --reload")
    except Exception as e:
        print(f"✗ Test failed with error: {e}")


if __name__ == "__main__":
    main()
