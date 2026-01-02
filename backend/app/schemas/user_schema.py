"""
User-related Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID
import re
from app.config import settings


class UserCreate(BaseModel):
    """Schema for user registration."""

    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=settings.password_min_length)
    country_code: str = Field(default="BD", max_length=2)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username is alphanumeric."""
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric (letters and numbers only)')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password meets security policy."""
        min_len = settings.password_min_length
        if len(v) < min_len:
            raise ValueError(f'Password must be at least {min_len} characters')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "password": "password123",
                "country_code": "BD"
            }
        }


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@example.com",
                "password": "DemoPassword123!"
            }
        }


class UserResponse(BaseModel):
    """Schema for user response (public profile)."""

    user_id: UUID
    username: str
    email: str
    role: str
    balance_bdt: int
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    is_banned: bool = False
    ban_reason: Optional[str] = None
    verified: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str
        }
        json_schema_extra = {
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "john_doe",
                "email": "john@example.com",
                "role": "user",
                "balance_bdt": 50000,
                "avatar_url": "https://example.com/avatar.jpg",
                "bio": "Virtual land enthusiast",
                "is_banned": False,
                "ban_reason": None,
                "verified": True,
                "created_at": "2025-01-15T10:20:30Z",
                "updated_at": "2025-01-15T10:20:30Z"
            }
        }


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    username: Optional[str] = Field(None, min_length=3, max_length=32)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = None

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """Validate username if provided."""
        if v is not None and not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "username": "john_doe_updated",
                "bio": "Updated bio",
                "avatar_url": "https://example.com/new-avatar.jpg"
            }
        }


class TokenResponse(BaseModel):
    """Schema for authentication token response."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int
    user: UserResponse
    previous_session_terminated: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer",
                "expires_in": 3600,
                "previous_session_terminated": True,
                "user": {
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "username": "john_doe",
                    "email": "john@example.com",
                    "role": "user",
                    "balance_bdt": 50000
                }
            }
        }


class SessionConflictResponse(BaseModel):
    """Schema for session conflict (already logged in elsewhere)."""

    status: str = "session_conflict"
    message: str
    user: UserResponse
    has_active_session: bool = True
    active_session_device: Optional[str] = None
    active_session_ip: Optional[str] = None
    active_session_started: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "session_conflict",
                "message": "Your account is already logged in from another browser/device. Please logout from the other device first, or click 'Take Over' to terminate the other session.",
                "user": {
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "username": "john_doe",
                    "email": "john@example.com",
                    "role": "user",
                    "balance_bdt": 50000
                },
                "has_active_session": True,
                "active_session_device": "Chrome on Windows",
                "active_session_ip": "192.168.1.1",
                "active_session_started": "2026-01-02T10:30:00Z"
            }
        }


class PasswordChange(BaseModel):
    """Schema for changing password."""

    old_password: str
    new_password: str = Field(..., min_length=settings.password_min_length)

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password meets security policy."""
        min_len = settings.password_min_length
        if len(v) < min_len:
            raise ValueError(f'Password must be at least {min_len} characters')
        return v
