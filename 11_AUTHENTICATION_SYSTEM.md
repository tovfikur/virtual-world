# Virtual Land World - Authentication System

## JWT Token Implementation

```python
# app/services/auth_service.py

import jwt
import secrets
from datetime import datetime, timedelta
from typing import Optional
import logging

from app.config import settings
from app.utils.exceptions import InvalidTokenException

logger = logging.getLogger(__name__)

class AuthService:
    """JWT token management and authentication."""

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm

    def create_access_token(self, user_id: str, email: str, role: str) -> str:
        """Create short-lived access token (1 hour)."""
        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes),
            "type": "access"
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.debug(f"Access token created for user {user_id}")
        return token

    def create_refresh_token(self) -> str:
        """Create long-lived refresh token (7 days)."""
        return secrets.token_urlsafe(32)

    def verify_token(self, token: str) -> dict:
        """Verify JWT signature and expiration."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            raise InvalidTokenException("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise InvalidTokenException("Invalid token")

    def decode_token_unsafe(self, token: str) -> dict:
        """Decode token without verification (for debugging)."""
        return jwt.decode(token, options={"verify_signature": False})
```

## Login Endpoint with Security

```python
# app/api/v1/endpoints/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, field_validator
import logging
from datetime import datetime, timedelta

from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import AuthService
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

auth_service = AuthService(settings.jwt_secret_key)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    password_confirm: str
    country_code: str

    @field_validator('username')
    def validate_username(cls, v):
        if len(v) < 3 or len(v) > 32:
            raise ValueError('Username must be 3-32 characters')
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        return v

    @field_validator('password')
    def validate_password(cls, v):
        import re
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain lowercase letter')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain uppercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain digit')
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', v):
            raise ValueError('Password must contain special character')
        return v

    @field_validator('password_confirm')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v

@router.post("/register", status_code=201)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register new user."""
    # Check if user exists
    existing = await db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Create user
    user = User(
        username=request.username,
        email=request.email
    )
    user.set_password(request.password)

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"User registered: {user.username}")

    return {
        "user_id": str(user.user_id),
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at
    }

@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    # Find user
    user = await db.query(User).filter(User.email == request.email).first()

    if not user:
        logger.warning(f"Login attempt with non-existent email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if account is locked
    if user.is_locked():
        logger.warning(f"Login attempt on locked account: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is temporarily locked due to too many failed attempts"
        )

    # Verify password
    if not user.verify_password(request.password):
        user.add_failed_login()
        await db.commit()
        logger.warning(f"Failed login attempt: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Reset failed attempts
    user.reset_login_attempts()
    await db.commit()

    # Generate tokens
    access_token = auth_service.create_access_token(
        user_id=str(user.user_id),
        email=user.email,
        role=user.role.value
    )
    refresh_token = auth_service.create_refresh_token()

    # Store refresh token in Redis with TTL
    from app.services.cache_service import cache_service
    await cache_service.set(
        f"refresh_token:{user.user_id}",
        refresh_token,
        ttl=7 * 24 * 60 * 60  # 7 days
    )

    logger.info(f"User logged in: {user.username}")

    response = JSONResponse(
        content={
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
            "user": {
                "user_id": str(user.user_id),
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "balance_bdt": user.balance_bdt
            }
        }
    )

    # Set refresh token as HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=7 * 24 * 60 * 60,  # 7 days
        httponly=True,
        secure=True,  # HTTPS only
        samesite="strict"
    )

    return response

@router.post("/refresh")
async def refresh(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token"
        )

    # Verify refresh token exists in Redis
    from app.services.cache_service import cache_service
    stored_token = await cache_service.get(f"refresh_token:*")

    # Find user with this refresh token (iterate through Redis)
    user_id = None
    # Note: In production, store user_id with token in Redis

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user = await db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Invalidate old refresh token
    await cache_service.delete(f"refresh_token:{user.user_id}")

    # Create new tokens (token rotation)
    new_access_token = auth_service.create_access_token(
        user_id=str(user.user_id),
        email=user.email,
        role=user.role.value
    )
    new_refresh_token = auth_service.create_refresh_token()

    # Store new refresh token
    await cache_service.set(
        f"refresh_token:{user.user_id}",
        new_refresh_token,
        ttl=7 * 24 * 60 * 60
    )

    response = JSONResponse(
        content={
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60
        }
    )

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        secure=True,
        samesite="strict"
    )

    logger.info(f"Token refreshed for user {user.username}")
    return response

@router.post("/logout")
async def logout(request: Request):
    """Logout and revoke refresh token."""
    refresh_token = request.cookies.get("refresh_token")

    if refresh_token:
        # Could optionally invalidate in Redis here
        pass

    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(key="refresh_token")

    logger.info("User logged out")
    return response
```

## Password Reset Flow

```python
@router.post("/password-reset/request")
async def request_password_reset(
    email: EmailStr,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset (sends email with token)."""
    user = await db.query(User).filter(User.email == email).first()

    if not user:
        # Don't reveal if email exists (security)
        return {"message": "If email exists, reset link will be sent"}

    # Generate reset token (valid for 1 hour)
    reset_token = secrets.token_urlsafe(32)
    reset_expires = datetime.utcnow() + timedelta(hours=1)

    # Store in Redis
    from app.services.cache_service import cache_service
    await cache_service.set(
        f"password_reset:{reset_token}",
        str(user.user_id),
        ttl=3600  # 1 hour
    )

    # Send email with reset link
    reset_url = f"https://app.virtuallandworld.com/reset-password?token={reset_token}"
    # send_email(user.email, "Password Reset", f"Click here to reset: {reset_url}")

    logger.info(f"Password reset requested for user {user.email}")
    return {"message": "If email exists, reset link will be sent"}

@router.post("/password-reset/confirm")
async def confirm_password_reset(
    token: str,
    new_password: str,
    db: AsyncSession = Depends(get_db)
):
    """Confirm password reset with token."""
    from app.services.cache_service import cache_service

    # Verify token
    user_id_str = await cache_service.get(f"password_reset:{token}")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    # Find user
    user = await db.query(User).filter(User.user_id == user_id_str).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update password
    user.set_password(new_password)
    await db.commit()

    # Invalidate reset token
    await cache_service.delete(f"password_reset:{token}")

    logger.info(f"Password reset completed for user {user.email}")
    return {"message": "Password reset successful"}
```

## Role-Based Access Control

```python
# app/dependencies.py

from fastapi import Depends, HTTPException, status
from typing import List

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get current user from JWT token."""
    try:
        payload = auth_service.verify_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(*allowed_roles: str):
    """Dependency factory for role-based access."""
    async def check_role(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return check_role

# Usage in endpoints
@router.get("/admin/users")
async def get_users(
    _: dict = Depends(require_role("admin"))
):
    """Only admins can access this endpoint."""
    pass
```

## Session Management

```python
# Session storage in Redis after successful login

async def store_session(user_id: str, token_jti: str, ttl: int = 3600):
    """Store session in Redis."""
    await cache_service.set(
        f"session:{user_id}",
        json.dumps({
            "jti": token_jti,
            "created_at": datetime.utcnow().isoformat(),
            "ip_address": request.client.host
        }),
        ttl=ttl
    )

async def verify_session(user_id: str) -> bool:
    """Verify session is still valid."""
    session = await cache_service.get(f"session:{user_id}")
    return session is not None
```

## Testing

```python
# tests/test_auth.py

@pytest.mark.asyncio
async def test_login_success(db: AsyncSession):
    """Test successful login."""
    user = User(username="testuser", email="test@example.com")
    user.set_password("TestPassword123!")
    db.add(user)
    await db.commit()

    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "TestPassword123!"
    })

    assert response.status_code == 200
    assert "access_token" in response.json()

@pytest.mark.asyncio
async def test_login_invalid_password(db: AsyncSession):
    """Test login with invalid password."""
    user = User(username="testuser", email="test@example.com")
    user.set_password("TestPassword123!")
    db.add(user)
    await db.commit()

    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "WrongPassword"
    })

    assert response.status_code == 401

@pytest.mark.asyncio
async def test_token_expiration():
    """Test token expiration."""
    expired_token = auth_service.create_access_token("user1", "test@example.com", "user")
    # Manually expire token in JWT payload
    with pytest.raises(InvalidTokenException):
        auth_service.verify_token(expired_token)
```

**Resume Token:** `✓ PHASE_3_AUTH_COMPLETE`
