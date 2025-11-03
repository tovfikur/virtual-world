"""
Authentication Tests
Simple test examples for the authentication system
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_register_user():
    """Test user registration"""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPassword123!"
        }
    )
    assert response.status_code in [200, 201, 409]  # 409 if user already exists


def test_login():
    """Test user login"""
    # First register a user
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser2",
            "email": "test2@example.com",
            "password": "TestPassword123!"
        }
    )

    # Then login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test2@example.com",
            "password": "TestPassword123!"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_invalid_credentials():
    """Test login with invalid credentials"""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "WrongPassword123!"
        }
    )
    assert response.status_code in [401, 404]


def test_get_me():
    """Test getting current user info"""
    # Login first
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test2@example.com",
            "password": "TestPassword123!"
        }
    )
    token = login_response.json()["access_token"]

    # Get user info
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert "email" in data


def test_password_requirements():
    """Test password validation"""
    # Too short
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser3",
            "email": "test3@example.com",
            "password": "Short1!"
        }
    )
    assert response.status_code == 422

    # No uppercase
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser4",
            "email": "test4@example.com",
            "password": "lowercase123!"
        }
    )
    assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
