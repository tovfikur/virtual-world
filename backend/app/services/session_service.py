"""
Session management service
Handles session creation, validation, termination and conflict detection
Enforces single-session-per-user policy for authenticated users
"""

import logging
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.session import UserSession
from app.models.user import User
from app.config import settings
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)


class SessionService:
    """Manages user sessions with single-session enforcement for authenticated users."""

    @staticmethod
    def generate_device_fingerprint(user_agent: str, ip_address: str) -> str:
        """
        Generate device fingerprint from user-agent and IP.

        Args:
            user_agent: Browser/app user agent string
            ip_address: Client IP address

        Returns:
            str: SHA256 hash of combined user-agent and IP
        """
        combined = f"{user_agent}:{ip_address}"
        return hashlib.sha256(combined.encode()).hexdigest()

    @staticmethod
    async def create_session(
        db: AsyncSession,
        user_id: Optional[str],
        session_token: str,
        user_agent: str,
        ip_address: str,
        expires_in_minutes: int = 1440,  # 24 hours default
    ) -> UserSession:
        """
        Create a new user session.

        Args:
            db: Database session
            user_id: User UUID (None for anonymous)
            session_token: JWT session identifier
            user_agent: Browser/app identifier
            ip_address: Client IP address
            expires_in_minutes: Session duration in minutes

        Returns:
            UserSession: Created session object

        Raises:
            ValueError: If authenticated user already has active session
        """
        device_fingerprint = SessionService.generate_device_fingerprint(
            user_agent, ip_address
        )

        # For authenticated users: enforce single session
        if user_id:
            existing_sessions = await SessionService.get_active_sessions(
                db, user_id
            )

            if existing_sessions:
                logger.warning(
                    f"Attempt to create second session for user {user_id}. "
                    f"Found {len(existing_sessions)} existing session(s)"
                )
                # Terminate existing sessions before creating new one
                await SessionService.terminate_all_sessions(db, user_id)

        # Create new session
        now = datetime.now(timezone.utc)
        session = UserSession(
            user_id=user_id,
            session_token=session_token,
            device_fingerprint=device_fingerprint,
            user_agent=user_agent,
            ip_address=ip_address,
            started_at=now,
            last_activity=now,
            expires_at=now + timedelta(minutes=expires_in_minutes),
            is_active=True,
        )

        db.add(session)
        await db.commit()
        await db.refresh(session)

        logger.info(f"Session created: {session.session_id} (user_id={user_id})")
        return session

    @staticmethod
    async def get_session(
        db: AsyncSession, session_id: str
    ) -> Optional[UserSession]:
        """
        Get a session by ID.

        Args:
            db: Database session
            session_id: Session UUID

        Returns:
            UserSession or None if not found/expired
        """
        result = await db.execute(
            select(UserSession).where(UserSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()

        # Check if expired
        if session and session.expires_at < datetime.now(timezone.utc):
            session.is_active = False
            await db.commit()
            return None

        return session

    @staticmethod
    async def get_session_by_token(
        db: AsyncSession, session_token: str
    ) -> Optional[UserSession]:
        """
        Get a session by token.

        Args:
            db: Database session
            session_token: Session token string

        Returns:
            UserSession or None if not found/expired/inactive
        """
        result = await db.execute(
            select(UserSession).where(
                and_(
                    UserSession.session_token == session_token,
                    UserSession.is_active == True,
                )
            )
        )
        session = result.scalar_one_or_none()

        # Check if expired
        if session and session.expires_at < datetime.now(timezone.utc):
            session.is_active = False
            await db.commit()
            return None

        return session

    @staticmethod
    async def get_active_sessions(
        db: AsyncSession, user_id: str
    ) -> List[UserSession]:
        """
        Get all active sessions for a user.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            List of active UserSession objects
        """
        result = await db.execute(
            select(UserSession).where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.utcnow(),
                )
            )
        )
        return result.scalars().all()

    @staticmethod
    async def validate_session(
        db: AsyncSession, session: UserSession
    ) -> bool:
        """
        Validate that a session is active and not expired.

        Args:
            db: Database session
            session: UserSession to validate

        Returns:
            bool: True if valid, False if expired/inactive
        """
        if not session or not session.is_active:
            return False

        if session.expires_at < datetime.now(timezone.utc):
            session.is_active = False
            await db.commit()
            return False

        return True

    @staticmethod
    async def update_activity(
        db: AsyncSession, session: UserSession
    ) -> None:
        """
        Update session's last activity timestamp.

        Args:
            db: Database session
            session: UserSession to update
        """
        session.last_activity = datetime.now(timezone.utc)
        await db.commit()

    @staticmethod
    async def terminate_session(
        db: AsyncSession, session_id: str
    ) -> bool:
        """
        Terminate a specific session.

        Args:
            db: Database session
            session_id: Session UUID

        Returns:
            bool: True if terminated, False if not found
        """
        result = await db.execute(
            select(UserSession).where(UserSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            return False

        session.is_active = False
        await db.commit()

        logger.info(f"Session terminated: {session_id}")
        return True

    @staticmethod
    async def terminate_all_sessions(
        db: AsyncSession, user_id: str
    ) -> int:
        """
        Terminate all active sessions for a user.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            int: Number of sessions terminated
        """
        result = await db.execute(
            select(UserSession).where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True,
                )
            )
        )
        sessions = result.scalars().all()

        for session in sessions:
            session.is_active = False

        await db.commit()

        logger.info(f"Terminated {len(sessions)} sessions for user {user_id}")
        return len(sessions)

    @staticmethod
    async def cleanup_expired_sessions(db: AsyncSession) -> int:
        """
        Mark all expired sessions as inactive (cleanup job).

        Args:
            db: Database session

        Returns:
            int: Number of sessions cleaned up
        """
        result = await db.execute(
            select(UserSession).where(
                and_(
                    UserSession.is_active == True,
                    UserSession.expires_at < datetime.now(timezone.utc),
                )
            )
        )
        expired_sessions = result.scalars().all()

        for session in expired_sessions:
            session.is_active = False

        await db.commit()

        logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        return len(expired_sessions)

    @staticmethod
    async def get_user_session_count(
        db: AsyncSession, user_id: str
    ) -> int:
        """
        Get count of active sessions for a user.

        Args:
            db: Database session
            user_id: User UUID

        Returns:
            int: Number of active sessions
        """
        result = await db.execute(
            select(UserSession).where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.utcnow(),
                )
            )
        )
        sessions = result.scalars().all()
        return len(sessions)

    @staticmethod
    async def check_duplicate_session(
        db: AsyncSession, user_id: str, device_fingerprint: str
    ) -> Tuple[bool, Optional[UserSession]]:
        """
        Check if user already has session on same device.

        Args:
            db: Database session
            user_id: User UUID
            device_fingerprint: Device fingerprint to check

        Returns:
            Tuple of (has_duplicate, existing_session)
        """
        result = await db.execute(
            select(UserSession).where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.device_fingerprint == device_fingerprint,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.utcnow(),
                )
            )
        )
        session = result.scalar_one_or_none()
        return (session is not None, session)
