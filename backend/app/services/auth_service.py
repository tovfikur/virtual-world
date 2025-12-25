"""
Authentication Service
Handles JWT token generation, verification, and user authentication
"""

import jwt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class AuthService:
    """
    JWT token management and authentication service.

    Handles:
    - Access token generation (short-lived, 1 hour)
    - Refresh token generation (long-lived, 7 days)
    - Token verification and validation
    - Token decoding (with and without verification)
    """

    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: Optional[str] = None
    ):
        """
        Initialize authentication service.

        Args:
            secret_key: JWT secret key (uses settings.jwt_secret_key if None)
            algorithm: JWT algorithm (uses settings.jwt_algorithm if None)
        """
        self.secret_key = secret_key or settings.jwt_secret_key
        self.algorithm = algorithm or settings.jwt_algorithm
        self.access_token_expire_minutes = settings.jwt_access_token_expire_minutes
        self.refresh_token_expire_days = settings.jwt_refresh_token_expire_days

    def create_access_token(
        self,
        user_id: str,
        email: str,
        role: str,
        additional_claims: Optional[Dict] = None,
        expires_minutes: Optional[int] = None
    ) -> str:
        """
        Create short-lived JWT access token.

        Args:
            user_id: User UUID as string
            email: User email address
            role: User role (user/admin/moderator)
            additional_claims: Optional additional JWT claims

        Returns:
            str: Encoded JWT token

        Example:
            ```python
            token = auth_service.create_access_token(
                user_id=str(user.user_id),
                email=user.email,
                role=user.role.value
            )
            ```
        """
        now = datetime.utcnow()
        expire_minutes = expires_minutes or self.access_token_expire_minutes
        expires = now + timedelta(minutes=expire_minutes)

        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "iat": now,
            "exp": expires,
            "type": "access"
        }

        if additional_claims:
            payload.update(additional_claims)

        token = jwt.encode(
            payload,
            self.secret_key,
            algorithm=self.algorithm
        )

        logger.debug(f"Access token created for user {user_id}")
        return token

    def create_refresh_token(self) -> str:
        """
        Create long-lived refresh token (random string, not JWT).

        Returns:
            str: Secure random token (URL-safe base64)

        Example:
            ```python
            refresh_token = auth_service.create_refresh_token()
            # Store in Redis with user_id as key
            ```
        """
        return secrets.token_urlsafe(32)

    def verify_token(self, token: str) -> Dict:
        """
        Verify JWT token signature and expiration.

        Args:
            token: JWT token string

        Returns:
            Dict: Decoded token payload

        Raises:
            InvalidTokenException: If token is invalid or expired

        Example:
            ```python
            try:
                payload = auth_service.verify_token(token)
                user_id = payload["sub"]
            except InvalidTokenException:
                # Handle invalid token
                pass
            ```
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )

            # Verify token type
            if payload.get("type") != "access":
                logger.warning(f"Invalid token type: {payload.get('type')}")
                raise InvalidTokenException("Invalid token type")

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            raise InvalidTokenException("Token has expired")

        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise InvalidTokenException("Invalid token")

        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise InvalidTokenException("Token verification failed")

    def decode_token_unsafe(self, token: str) -> Dict:
        """
        Decode token without verification (for debugging/inspection).

        WARNING: Do not use for authentication! This bypasses security checks.

        Args:
            token: JWT token string

        Returns:
            Dict: Decoded token payload (unverified)

        Example:
            ```python
            # For debugging only
            payload = auth_service.decode_token_unsafe(token)
            print(f"Token expires at: {payload['exp']}")
            ```
        """
        return jwt.decode(
            token,
            options={"verify_signature": False}
        )

    def get_token_expiration(self, token: str) -> Optional[datetime]:
        """
        Get token expiration time without full verification.

        Args:
            token: JWT token string

        Returns:
            Optional[datetime]: Expiration datetime or None if invalid
        """
        try:
            payload = self.decode_token_unsafe(token)
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                return datetime.fromtimestamp(exp_timestamp)
        except Exception:
            pass
        return None

    def is_token_expired(self, token: str) -> bool:
        """
        Check if token is expired without full verification.

        Args:
            token: JWT token string

        Returns:
            bool: True if expired, False otherwise
        """
        expiration = self.get_token_expiration(token)
        if not expiration:
            return True
        return datetime.utcnow() > expiration

    def extract_user_id(self, token: str) -> Optional[str]:
        """
        Extract user ID from token without full verification.

        Args:
            token: JWT token string

        Returns:
            Optional[str]: User ID or None if invalid
        """
        try:
            payload = self.decode_token_unsafe(token)
            return payload.get("sub")
        except Exception:
            return None


class InvalidTokenException(Exception):
    """Exception raised when token is invalid or expired."""
    pass


# Global auth service instance
auth_service = AuthService()
