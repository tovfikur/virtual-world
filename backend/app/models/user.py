"""
User model
Represents user accounts with authentication and profile information
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import bcrypt
from datetime import datetime, timedelta
from enum import Enum as PyEnum

from app.db.base import BaseModel


class UserRole(str, PyEnum):
    """User role enumeration."""
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class User(BaseModel):
    """
    User model for authentication and profile management.

    Attributes:
        user_id: Unique UUID identifier
        username: Unique display name (3-32 chars)
        email: Unique email address
        password_hash: Bcrypt hashed password (never store plaintext)
        role: User role (user/admin/moderator)
        balance_bdt: Account balance in Bangladeshi Taka
        avatar_url: URL to avatar image
        bio: User biography or profile text
        verified: Whether email is verified
        failed_login_attempts: Counter for failed login attempts
        locked_until: Account lock timestamp (for security)
    """

    __tablename__ = "users"

    # Primary Key
    user_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Account Information
    username = Column(
        String(32),
        unique=True,
        nullable=False,
        index=True
    )
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    password_hash = Column(
        String(255),
        nullable=False
    )
    role = Column(
        SQLEnum(UserRole),
        default=UserRole.USER,
        nullable=False,
        index=True
    )

    # Profile
    avatar_url = Column(String, nullable=True)
    bio = Column(String, nullable=True)

    # Financial
    balance_bdt = Column(
        Integer,
        default=0,
        nullable=False
    )

    # Account Status
    verified = Column(
        Boolean,
        default=False,
        nullable=False
    )

    # Security
    failed_login_attempts = Column(
        Integer,
        default=0,
        nullable=False
    )
    locked_until = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # Suspension
    is_suspended = Column(
        Boolean,
        default=False,
        nullable=False
    )
    suspension_reason = Column(
        String,
        nullable=True
    )
    suspended_until = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # Last Login
    last_login = Column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    lands = relationship(
        "Land",
        back_populates="owner",
        foreign_keys="Land.owner_id"
    )
    transactions_as_seller = relationship(
        "Transaction",
        back_populates="seller",
        foreign_keys="Transaction.seller_id"
    )
    transactions_as_buyer = relationship(
        "Transaction",
        back_populates="buyer",
        foreign_keys="Transaction.buyer_id"
    )
    bids = relationship(
        "Bid",
        back_populates="bidder"
    )
    listings = relationship(
        "Listing",
        back_populates="seller"
    )
    messages = relationship(
        "Message",
        back_populates="sender"
    )
    audit_logs = relationship(
        "AuditLog",
        back_populates="actor",
        foreign_keys="AuditLog.actor_id"
    )

    def set_password(self, password: str) -> None:
        """
        Hash and set user password using bcrypt.

        Args:
            password: Plain text password

        Example:
            ```python
            user = User(username="john", email="john@example.com")
            user.set_password("SecurePassword123!")
            ```
        """
        from app.config import settings
        salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            salt
        ).decode('utf-8')

    def verify_password(self, password: str) -> bool:
        """
        Verify password against stored hash (constant-time comparison).

        Args:
            password: Plain text password to verify

        Returns:
            bool: True if password matches, False otherwise

        Example:
            ```python
            if user.verify_password(password):
                # Password correct
                pass
            ```
        """
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                self.password_hash.encode('utf-8')
            )
        except Exception:
            return False

    def is_locked(self) -> bool:
        """
        Check if account is currently locked due to failed login attempts.

        Returns:
            bool: True if account is locked, False otherwise
        """
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    def add_failed_login(self) -> None:
        """
        Increment failed login counter and lock account if threshold exceeded.
        Account is locked for 15 minutes after 5 failed attempts.
        """
        from app.config import settings
        self.failed_login_attempts += 1

        if self.failed_login_attempts >= settings.max_login_attempts:
            self.locked_until = datetime.utcnow() + timedelta(
                minutes=settings.lockout_duration_minutes
            )

    def reset_login_attempts(self) -> None:
        """
        Reset failed login counter and unlock account.
        Should be called after successful login.
        """
        self.failed_login_attempts = 0
        self.locked_until = None

    def add_balance(self, amount_bdt: int) -> None:
        """
        Add funds to user balance.

        Args:
            amount_bdt: Amount to add (must be positive)

        Raises:
            ValueError: If amount is negative
        """
        if amount_bdt < 0:
            raise ValueError("Amount must be positive")
        self.balance_bdt += amount_bdt

    def deduct_balance(self, amount_bdt: int) -> None:
        """
        Deduct funds from user balance.

        Args:
            amount_bdt: Amount to deduct (must be positive)

        Raises:
            ValueError: If amount is negative or exceeds balance
        """
        if amount_bdt < 0:
            raise ValueError("Amount must be positive")
        if amount_bdt > self.balance_bdt:
            raise ValueError("Insufficient balance")
        self.balance_bdt -= amount_bdt

    def __repr__(self) -> str:
        """String representation of User."""
        return f"<User {self.username} ({self.user_id})>"

    def to_dict(self) -> dict:
        """
        Convert user to dictionary (safe for API responses).
        Excludes sensitive information like password_hash.

        Returns:
            dict: User data dictionary
        """
        return {
            "user_id": str(self.user_id),
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "balance_bdt": self.balance_bdt,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "verified": self.verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
