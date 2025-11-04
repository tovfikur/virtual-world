"""
Authentication endpoints
User registration, login, token refresh, logout
"""

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from datetime import datetime

from app.db.session import get_db
from app.models.user import User
from app.schemas.user_schema import UserCreate, UserLogin, UserResponse, TokenResponse
from app.services.auth_service import auth_service
from app.services.cache_service import cache_service
from app.services.land_allocation_service import land_allocation_service
from app.config import settings, CACHE_TTLS
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


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
        user.add_failed_login()
        await db.commit()
        logger.warning(f"Failed login attempt for user: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Reset failed login attempts on successful login
    user.reset_login_attempts()
    await db.commit()

    # Generate tokens
    access_token = auth_service.create_access_token(
        user_id=str(user.user_id),
        email=user.email,
        role=user.role.value
    )
    refresh_token = auth_service.create_refresh_token()

    # Store refresh token in Redis with user_id as key
    await cache_service.set(
        f"refresh_token:{user.user_id}",
        refresh_token,
        ttl=CACHE_TTLS["refresh_token"]
    )

    # Store session in Redis
    await cache_service.set(
        f"session:{user.user_id}",
        {
            "user_id": str(user.user_id),
            "email": user.email,
            "role": user.role.value,
            "created_at": datetime.utcnow().isoformat()
        },
        ttl=CACHE_TTLS["session"]
    )

    logger.info(f"User logged in: {user.username} ({user.user_id})")

    # Create response
    token_response = TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user)
    )

    # Set refresh token as HTTP-only cookie
    json_response = JSONResponse(
        content=token_response.model_dump(mode='json')
    )
    json_response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=CACHE_TTLS["refresh_token"],
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

    # Generate new tokens
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
        ttl=CACHE_TTLS["refresh_token"]
    )

    logger.info(f"Token refreshed for user: {user.username}")

    # Create response
    token_response = TokenResponse(
        access_token=new_access_token,
        token_type="Bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user)
    )

    json_response = JSONResponse(
        content=token_response.model_dump(mode='json')
    )
    json_response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        max_age=CACHE_TTLS["refresh_token"],
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
