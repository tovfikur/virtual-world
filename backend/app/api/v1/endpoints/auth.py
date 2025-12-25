"""
Authentication endpoints
User registration, login, token refresh, logout
"""

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
import secrets
from datetime import datetime
import re

from app.db.session import get_db
from app.models.user import User
from app.models.admin_config import AdminConfig
from app.schemas.user_schema import UserCreate, UserLogin, UserResponse, TokenResponse
from app.services.auth_service import auth_service
from app.services.cache_service import cache_service
from app.services.land_allocation_service import land_allocation_service
from app.config import settings, CACHE_TTLS
from app.dependencies import get_current_user
from app.services.websocket_service import connection_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


async def _get_security_settings(db: AsyncSession):
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()

    access_minutes = config.access_token_expire_minutes if config else settings.jwt_access_token_expire_minutes
    refresh_days = config.refresh_token_expire_days if config else settings.jwt_refresh_token_expire_days

    password_policy = {
        "min_length": config.password_min_length if config else settings.password_min_length,
        "require_uppercase": config.password_require_uppercase if config else True,
        "require_lowercase": config.password_require_lowercase if config else True,
        "require_number": config.password_require_number if config else True,
        "require_special": config.password_require_special if config else True,
    }

    login_policy = {
        "max_attempts": config.login_max_attempts if config else settings.max_login_attempts,
        "lockout_duration_minutes": config.lockout_duration_minutes if config else settings.lockout_duration_minutes,
        "max_sessions_per_user": config.max_sessions_per_user if config else 1,
    }

    return access_minutes, refresh_days, password_policy, login_policy


def _validate_password_policy(password: str, policy: dict):
    if len(password) < policy.get("min_length", 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {policy['min_length']} characters"
        )

    if policy.get("require_uppercase") and not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must include at least one uppercase letter"
        )

    if policy.get("require_lowercase") and not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must include at least one lowercase letter"
        )

    if policy.get("require_number") and not re.search(r"[0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must include at least one number"
        )

    if policy.get("require_special") and not re.search(r"[^A-Za-z0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must include at least one special character"
        )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user account.

    - **username**: 3-32 alphanumeric characters (unique)
    - **email**: Valid email address (unique)
    - **password**: Min 12 chars with uppercase, lowercase, digit, special char
    - **country_code**: ISO 3166-1 alpha-2 (default: BD)

    Returns the created user profile (excluding password).
    """
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Check if username already exists
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    existing_username = result.scalar_one_or_none()

    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken"
        )

    _, _, password_policy, _ = await _get_security_settings(db)
    _validate_password_policy(user_data.password, password_policy)

    # Create new user
    user = User(
        username=user_data.username,
        email=user_data.email
    )
    user.set_password(user_data.password)

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"New user registered: {user.username} ({user.user_id})")

    # Allocate starter land to new user
    try:
        allocated_lands = await land_allocation_service.allocate_starter_land(db, user)
        if allocated_lands:
            logger.info(f"Allocated {len(allocated_lands)} land units to new user {user.username}")
        else:
            logger.warning(f"Failed to allocate starter land to {user.username}")
    except Exception as e:
        logger.error(f"Error allocating starter land to {user.username}: {e}")
        # Don't fail registration if land allocation fails

    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user with email and password.

    Returns:
    - **access_token**: JWT token (expires in 1 hour)
    - **refresh_token**: Set as HTTP-only cookie (expires in 7 days)
    - **user**: User profile information

    The refresh token is stored in a secure, HTTP-only cookie.
    """
    access_minutes, refresh_days, _, login_policy = await _get_security_settings(db)

    # Find user by email
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"Login attempt with non-existent email: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if account is locked
    if user.is_locked():
        logger.warning(f"Login attempt on locked account: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is temporarily locked due to too many failed login attempts"
        )

    # Verify password
    if not user.verify_password(user_data.password):
        user.add_failed_login(
            max_attempts=login_policy["max_attempts"],
            lockout_minutes=login_policy["lockout_duration_minutes"],
        )
        await db.commit()
        logger.warning(f"Failed login attempt for user: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Reset failed login attempts on successful login
    user.reset_login_attempts()
    await db.commit()

    # Check for existing session to enforce single-device rule
    previous_session = await cache_service.get(f"session:{user.user_id}")
    previous_session_terminated = False

    if login_policy["max_sessions_per_user"] <= 1 and previous_session and connection_manager.has_active_connections(str(user.user_id)):
        forced = await connection_manager.force_logout_user(
            str(user.user_id),
            reason="Another device signed in with this account"
        )
        if forced:
            previous_session_terminated = True
        else:
            logger.warning(f"Could not terminate existing session for user {user.username}")
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Another device is already using this account. Please log out there first."
            )

    access_minutes, refresh_days, _, _ = await _get_security_settings(db)
    access_expires_seconds = access_minutes * 60
    refresh_ttl_seconds = refresh_days * 24 * 60 * 60
    session_ttl = max(refresh_ttl_seconds, CACHE_TTLS["session"])

    # Generate tokens with session binding
    session_id = secrets.token_urlsafe(32)
    access_token = auth_service.create_access_token(
        user_id=str(user.user_id),
        email=user.email,
        role=user.role.value,
        additional_claims={"session_id": session_id},
        expires_minutes=access_minutes,
    )
    refresh_token = auth_service.create_refresh_token()

    # Store refresh token in Redis with user_id as key
    await cache_service.set(
        f"refresh_token:{user.user_id}",
        refresh_token,
        ttl=refresh_ttl_seconds
    )

    # Store session in Redis
    await cache_service.set(
        f"session:{user.user_id}",
        {
            "session_id": session_id,
            "user_id": str(user.user_id),
            "email": user.email,
            "role": user.role.value,
            "created_at": datetime.utcnow().isoformat()
        },
        ttl=session_ttl
    )

    logger.info(f"User logged in: {user.username} ({user.user_id})")

    # Create response
    token_response = TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=access_expires_seconds,
        user=UserResponse.model_validate(user),
        previous_session_terminated=previous_session_terminated
    )

    # Set refresh token as HTTP-only cookie
    json_response = JSONResponse(
        content=token_response.model_dump(mode='json')
    )
    json_response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=refresh_ttl_seconds,
        httponly=True,
        secure=True,  # HTTPS only in production
        samesite="strict"
    )

    return json_response


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token from cookie.

    The old refresh token is invalidated and a new one is issued (token rotation).

    Returns new access token and sets new refresh token cookie.
    """
    # Extract refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided"
        )

    # Find user_id associated with this refresh token
    # In production, consider storing user_id with token in Redis
    user_id = None
    redis_keys = []

    # Scan Redis for refresh tokens (not ideal for production at scale)
    # Better approach: include user_id in refresh token or use a different structure
    if cache_service.client:
        async for key in cache_service.client.scan_iter("refresh_token:*"):
            stored_token = await cache_service.get(key)
            if stored_token == refresh_token:
                user_id = key.split(":")[1]
                break

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Get user from database
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Invalidate old refresh token (token rotation)
    await cache_service.delete(f"refresh_token:{user.user_id}")

    session_data = await cache_service.get(f"session:{user.user_id}")
    if not session_data or not session_data.get("session_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Active session not found"
        )

    access_minutes, refresh_days, _, _ = await _get_security_settings(db)
    access_expires_seconds = access_minutes * 60
    refresh_ttl_seconds = refresh_days * 24 * 60 * 60

    # Generate new tokens bound to existing session
    new_access_token = auth_service.create_access_token(
        user_id=str(user.user_id),
        email=user.email,
        role=user.role.value,
        additional_claims={"session_id": session_data["session_id"]},
        expires_minutes=access_minutes,
    )
    new_refresh_token = auth_service.create_refresh_token()

    # Store new refresh token
    await cache_service.set(
        f"refresh_token:{user.user_id}",
        new_refresh_token,
        ttl=refresh_ttl_seconds
    )

    await cache_service.set(
        f"session:{user.user_id}",
        session_data,
        ttl=max(refresh_ttl_seconds, CACHE_TTLS["session"])
    )

    logger.info(f"Token refreshed for user: {user.username}")

    # Create response
    token_response = TokenResponse(
        access_token=new_access_token,
        token_type="Bearer",
        expires_in=access_expires_seconds,
        user=UserResponse.model_validate(user)
    )

    json_response = JSONResponse(
        content=token_response.model_dump(mode='json')
    )
    json_response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        max_age=refresh_ttl_seconds,
        httponly=True,
        secure=True,
        samesite="strict"
    )

    return json_response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Logout current user.

    Invalidates refresh token and session.
    Client should discard the access token.
    """
    user_id = current_user["sub"]

    # Delete refresh token from Redis
    await cache_service.delete(f"refresh_token:{user_id}")

    # Delete session from Redis
    await cache_service.delete(f"session:{user_id}")

    logger.info(f"User logged out: {user_id}")

    # Clear refresh token cookie
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(key="refresh_token")

    return response


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current authenticated user's profile.

    Requires valid JWT token in Authorization header.
    """
    user_id = current_user["sub"]

    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse.model_validate(user)
