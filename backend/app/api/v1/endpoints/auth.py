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
import hashlib

from app.db.session import get_db
from app.models.user import User
from app.models.admin_config import AdminConfig
from app.schemas.user_schema import UserCreate, UserLogin, UserResponse, TokenResponse
from app.services.auth_service import auth_service
from app.services.cache_service import cache_service
from app.services.land_allocation_service import land_allocation_service
from app.services.session_service import SessionService
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
        "require_uppercase": config.password_require_uppercase if config else False,
        "require_lowercase": config.password_require_lowercase if config else False,
        "require_number": config.password_require_number if config else False,
        "require_special": config.password_require_special if config else False,
    }

    login_policy = {
        "max_attempts": config.login_max_attempts if config else settings.max_login_attempts,
        "lockout_duration_minutes": config.lockout_duration_minutes if config else settings.lockout_duration_minutes,
        "max_sessions_per_user": config.max_sessions_per_user if config else 1,
    }

    return access_minutes, refresh_days, password_policy, login_policy


def _validate_password_policy(password: str, policy: dict):
    if len(password) < policy.get("min_length", 6):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {policy.get('min_length', 6)} characters"
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
            logger.info(f"Allocated {len(allocated_lands)} land units to new user")
        else:
            logger.warning("Failed to allocate starter land to new user")
    except Exception as e:
        # Ensure session is usable after an allocation failure
        try:
            await db.rollback()
        except Exception:
            pass
        logger.error(f"Error allocating starter land: {e}")
        # Don't fail registration if land allocation fails
    # Ensure user attributes are loaded before serialization
    try:
        await db.refresh(user)
    except Exception:
        pass

    from fastapi.responses import JSONResponse
    return JSONResponse(content=user.to_dict(), status_code=status.HTTP_201_CREATED)


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
    confirm_takeover: bool = False,
):
    """
    Authenticate user with email and password.

    For authenticated users: Enforces single-session-per-user policy.
    If user is already logged in from another device:
    - Returns 409 CONFLICT with session info
    - Requires explicit confirm_takeover=true to proceed

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

    # Prepare device information for current request
    current_user_agent = request.headers.get("user-agent", "unknown")
    current_ip_address = request.client.host if request.client else "0.0.0.0"
    
    # Calculate device fingerprint for current request
    current_fingerprint = hashlib.sha256(
        f"{current_user_agent}:{current_ip_address}".encode()
    ).hexdigest()

    # CHECK FOR EXISTING SESSION (Conflict Detection)
    if login_policy["max_sessions_per_user"] <= 1:
        existing_sessions = await SessionService.get_active_sessions(db, str(user.user_id))
        
        # If session exists, check if it's from a different device
        if existing_sessions and not confirm_takeover:
            active_session = existing_sessions[0]
            
            # Compare device fingerprints - if same device, allow re-login without conflict
            is_same_device = (active_session.device_fingerprint == current_fingerprint)
            
            if not is_same_device:
                logger.warning(f"Login conflict detected for user {user.username}: attempt from new device without confirmation")
                
                # Return conflict response only if different device
                conflict_response = {
                    "status": "session_conflict",
                    "message": "Your account is already logged in from another browser or device. Please logout from the other device first, or click 'Take Over Session' to terminate the other session and login from this device.",
                    "user": user.to_dict(),
                    "has_active_session": True,
                    "active_session_device": active_session.user_agent,
                    "active_session_ip": active_session.ip_address,
                    "active_session_started": active_session.started_at.isoformat() if active_session.started_at else None
                }
                
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=conflict_response
                )
            else:
                # Same device - terminate old session silently and continue with new login
                logger.info(f"Re-login from same device for user {user.username}: terminating existing session")
                await SessionService.terminate_all_sessions(db, str(user.user_id))

    # SINGLE SESSION ENFORCEMENT: Terminate any existing sessions for this user
    previous_session_terminated = False
    if login_policy["max_sessions_per_user"] <= 1:
        terminated_count = await SessionService.terminate_all_sessions(db, str(user.user_id))
        if terminated_count > 0:
            previous_session_terminated = True
            logger.info(f"Terminated {terminated_count} existing session(s) for user {user.username}")

    # Prepare device information for session tracking
    user_agent = request.headers.get("user-agent", "unknown")
    ip_address = request.client.host if request.client else "0.0.0.0"

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

    # Create new session in database with device fingerprinting
    try:
        db_session = await SessionService.create_session(
            db=db,
            user_id=str(user.user_id),
            session_token=session_id,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_in_minutes=refresh_days * 24 * 60,  # Same as refresh token
        )
        logger.info(f"Session created in DB: {db_session.session_id} for user {user.username}")
    except Exception as e:
        logger.error(f"Failed to create session in database: {e}")
        # Don't fail login if session DB creation fails, still use cache

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
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=access_expires_seconds,
        user=UserResponse.model_validate(user.to_dict()),
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
    body: dict | None = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token from cookie.

    The old refresh token is invalidated and a new one is issued (token rotation).

    Returns new access token and sets new refresh token cookie.
    """
    # Extract refresh token from cookie first, then JSON body fallback
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token and body and body.get("refresh_token"):
        refresh_token = body.get("refresh_token")

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

    # Check if session exists in database and is still valid
    session_token = session_data.get("session_id")
    logger.info(f"Refresh: Looking for DB session with token {session_token}")
    db_session = None
    if session_token:
        try:
            db_session = await SessionService.get_session_by_token(db, session_token)
            if db_session:
                logger.info(f"Refresh: Found DB session {db_session.session_id}, is_active={db_session.is_active}")
            else:
                logger.warning(f"Refresh: DB session not found for token {session_token}")
        except Exception as e:
            logger.error(f"Error checking DB session: {e}")

    # If DB session is missing or expired, create a new one and update session_id
    if not db_session:
        logger.warning(f"DB session invalid for token {session_token}; creating new session")
        try:
            # Create new session with same user
            new_session_id = secrets.token_urlsafe(32)
            access_minutes, refresh_days, _, _ = await _get_security_settings(db)
            
            new_db_session = await SessionService.create_session(
                db=db,
                user_id=str(user.user_id),
                session_token=new_session_id,
                user_agent=session_data.get("user_agent", "unknown"),
                ip_address=session_data.get("ip_address", "0.0.0.0"),
                expires_in_minutes=refresh_days * 24 * 60,
            )
            
            # Update cache with new session_id
            session_data["session_id"] = new_session_id
            await cache_service.set(
                f"session:{user.user_id}",
                session_data,
                ttl=max(refresh_days * 24 * 60 * 60, CACHE_TTLS["session"])
            )
            logger.info(f"Created new DB session {new_session_id} for refresh")
            db_session = new_db_session
        except Exception as e:
            logger.error(f"Failed to create new session on refresh: {e}")
            # Fall back to reusing old session_id, will likely fail auth but at least we tried
    else:
        # Session exists, just update its last activity
        try:
            await SessionService.update_activity(db, db_session)
            logger.info(f"Updated activity for existing session {db_session.session_id}")
        except Exception as e:
            logger.error(f"Error updating session activity: {e}")

    access_minutes, refresh_days, _, _ = await _get_security_settings(db)
    access_expires_seconds = access_minutes * 60
    refresh_ttl_seconds = refresh_days * 24 * 60 * 60

    # Generate new tokens bound to (possibly new) session
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
        refresh_token=new_refresh_token,
        token_type="Bearer",
        expires_in=access_expires_seconds,
        user=UserResponse.model_validate(user.to_dict())
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
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    confirm: bool = True
):
    """
    Logout current user.

    Invalidates refresh token, session in cache, and terminates session in database.
    Client should discard the access token.
    
    Args:
        confirm: Must be True to prevent accidental logouts (e.g., on page refresh)
                Default is True to maintain backwards compatibility.
    """
    # Prevent accidental logouts on page refresh or other unintended triggers
    if not confirm:
        logger.warning(f"Logout attempt without confirmation for user {current_user['sub']}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logout confirmation required"
        )
    
    user_id = current_user["sub"]
    session_token = current_user.get("session_id")

    # Delete refresh token from Redis
    await cache_service.delete(f"refresh_token:{user_id}")

    # Delete session from Redis
    await cache_service.delete(f"session:{user_id}")

    # Terminate session in database
    if session_token:
        try:
            db_session = await SessionService.get_session_by_token(db, session_token)
            if db_session:
                await SessionService.terminate_session(db, str(db_session.session_id))
            else:
                logger.warning(f"Logout called with missing DB session for token {session_token}")
        except Exception as e:
            logger.error(f"Failed to terminate session for token {session_token}: {e}")
            # Don't fail logout if DB update fails

    logger.info(f"User logged out: {user_id}")

    # Clear refresh token cookie
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(key="refresh_token")

    return response


@router.post("/login/confirm-takeover", response_model=TokenResponse)
async def login_confirm_takeover(
    user_data: UserLogin,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Confirm taking over the session - terminates existing session and logs in from new device.
    
    This endpoint is called after receiving a 409 CONFLICT response from /login.
    It requires valid credentials and will terminate any existing sessions for the user.
    
    Returns:
    - **access_token**: JWT token (expires in 1 hour)
    - **refresh_token**: Set as HTTP-only cookie (expires in 7 days)
    - **user**: User profile information
    - **previous_session_terminated**: True (confirming existing session was terminated)
    """
    confirm_takeover = True  # Always true for this endpoint
    
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

    # Prepare device information for current request
    confirm_takeover_user_agent = request.headers.get("user-agent", "unknown")
    confirm_takeover_ip_address = request.client.host if request.client else "0.0.0.0"

    # SINGLE SESSION ENFORCEMENT: Terminate any existing sessions for this user
    previous_session_terminated = False
    if login_policy["max_sessions_per_user"] <= 1:
        terminated_count = await SessionService.terminate_all_sessions(db, str(user.user_id))
        if terminated_count > 0:
            previous_session_terminated = True
            logger.info(f"Terminated {terminated_count} existing session(s) for user {user.username}")

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

    # Create new session in database with device fingerprinting
    try:
        db_session = await SessionService.create_session(
            db=db,
            user_id=str(user.user_id),
            session_token=session_id,
            user_agent=confirm_takeover_user_agent,
            ip_address=confirm_takeover_ip_address,
            expires_in_minutes=refresh_days * 24 * 60,  # Same as refresh token
        )
        logger.info(f"Session created in DB: {db_session.session_id} for user {user.username}")
    except Exception as e:
        logger.error(f"Failed to create session in database: {e}")
        # Don't fail login if session DB creation fails, still use cache

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
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=access_expires_seconds,
        user=UserResponse.model_validate(user.to_dict()),
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

    return UserResponse.model_validate(user.to_dict())
