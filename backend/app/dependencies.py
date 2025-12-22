"""
FastAPI Dependencies
Dependency injection for authentication, database, etc.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.db.session import get_db
from app.services.auth_service import auth_service, InvalidTokenException
from app.services.cache_service import cache_service
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Dependency to extract and verify current user from JWT token.

    Args:
        credentials: HTTP Bearer token from Authorization header
        db: Database session

    Returns:
        dict: Token payload with user information

    Raises:
        HTTPException: If token is invalid or user not found

    Example:
        ```python
        @router.get("/profile")
        async def get_profile(current_user: dict = Depends(get_current_user)):
            user_id = current_user["sub"]
            return {"user_id": user_id}
        ```
    """
    token = credentials.credentials

    try:
        payload = auth_service.verify_token(token)
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )

        # Verify user still exists in database
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        if user.is_locked():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is locked"
            )

        # Enforce single active session
        active_session = await cache_service.get(f"session:{user_id}")
        token_session_id = payload.get("session_id")
        if not active_session or not token_session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired"
            )
        if active_session.get("session_id") != token_session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="You have been logged out from another device"
            )

        return payload

    except InvalidTokenException as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


async def get_current_active_user(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Dependency to get current user and ensure account is active.

    Args:
        current_user: User payload from get_current_user

    Returns:
        dict: User payload

    Raises:
        HTTPException: If account is not active
    """
    # Additional checks can be added here (e.g., email verification)
    return current_user


def require_role(*allowed_roles: UserRole):
    """
    Dependency factory to enforce role requirements.

    Args:
        allowed_roles: Roles that are allowed to access the endpoint

    Returns:
        Dependency function

    Example:
        ```python
        @router.get("/admin/users")
        async def get_users(_: dict = Depends(require_role(UserRole.ADMIN))):
            # Only admins can access
            pass
        ```
    """
    async def check_role(
        current_user: dict = Depends(get_current_user)
    ) -> dict:
        user_role = current_user.get("role")

        if user_role not in [role.value for role in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {[r.value for r in allowed_roles]}"
            )

        return current_user

    return check_role


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db)
) -> Optional[dict]:
    """
    Dependency to optionally get current user (for public endpoints that benefit from auth).

    Args:
        credentials: Optional HTTP Bearer token
        db: Database session

    Returns:
        Optional[dict]: User payload if authenticated, None otherwise

    Example:
        ```python
        @router.get("/lands")
        async def get_lands(user: Optional[dict] = Depends(get_optional_user)):
            # Endpoint works both authenticated and unauthenticated
            if user:
                # Show user's favorite lands
                pass
        ```
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
