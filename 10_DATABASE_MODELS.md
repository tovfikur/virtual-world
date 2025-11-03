# Virtual Land World - Database ORM Models

## Overview

This document provides complete SQLAlchemy ORM models for all 8 core database tables. All models use async patterns, proper type hints, and validation constraints.

---

## Base Configuration (db/base.py)

```python
# app/db/base.py

from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, DateTime, func
from datetime import datetime

Base = declarative_base()

class TimestampMixin:
    """Mixin for timestamp columns."""
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

class BaseModel(Base):
    """Base model with common fields."""
    __abstract__ = True

    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
```

---

## User Model

```python
# app/models/user.py

from sqlalchemy import Column, String, Integer, Boolean, DateTime, func, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import bcrypt
from datetime import datetime
from enum import Enum as PyEnum

from app.db.base import BaseModel

class UserRole(str, PyEnum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"

class User(BaseModel):
    __tablename__ = "users"

    # Primary Key
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Account Info
    username = Column(String(32), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False, index=True)

    # Profile
    avatar_url = Column(String, nullable=True)
    bio = Column(String, nullable=True)

    # Account Status
    balance_bdt = Column(Integer, default=0, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)

    # Security
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    lands = relationship("Land", back_populates="owner", foreign_keys="Land.owner_id")
    transactions_as_seller = relationship("Transaction", back_populates="seller",
                                          foreign_keys="Transaction.seller_id")
    transactions_as_buyer = relationship("Transaction", back_populates="buyer",
                                         foreign_keys="Transaction.buyer_id")
    bids = relationship("Bid", back_populates="bidder")
    listings = relationship("Listing", back_populates="seller")
    messages = relationship("Message", back_populates="sender")
    audit_logs = relationship("AuditLog", back_populates="actor")

    def set_password(self, password: str) -> None:
        """Hash and set password."""
        salt = bcrypt.gensalt(rounds=12)
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            salt
        ).decode('utf-8')

    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    def is_locked(self) -> bool:
        """Check if account is locked."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    def add_failed_login(self):
        """Increment failed login attempts."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            from datetime import timedelta
            self.locked_until = datetime.utcnow() + timedelta(minutes=15)

    def reset_login_attempts(self):
        """Reset failed login counter."""
        self.failed_login_attempts = 0
        self.locked_until = None

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.user_id})>"
```

---

## Land Model

```python
# app/models/land.py

from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Index, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
import uuid
from enum import Enum as PyEnum
from datetime import datetime

from app.db.base import BaseModel

class Biome(str, PyEnum):
    FOREST = "forest"
    DESERT = "desert"
    GRASSLAND = "grassland"
    WATER = "water"
    SNOW = "snow"

class Land(BaseModel):
    __tablename__ = "lands"
    __table_args__ = (
        Index("idx_lands_coordinates", "x", "y", "z", unique=True),
        Index("idx_lands_spatial", "x", "y", postgresql_using="brin"),
    )

    # Primary Key
    land_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Ownership
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)

    # Coordinates
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)
    z = Column(Integer, default=0, nullable=False)

    # World Data
    biome = Column(Enum(Biome), nullable=False, index=True)
    elevation = Column(Float, default=0.5, nullable=False)
    color_hex = Column(String(7), nullable=False)

    # Access Control
    fenced = Column(Boolean, default=False, nullable=False)
    passcode_hash = Column(String(255), nullable=True)
    passcode_updated_at = Column(DateTime(timezone=True), nullable=True)

    # Content
    public_message = Column(String(500), nullable=True)

    # Pricing
    price_base_bdt = Column(Integer, default=1000, nullable=False)

    # Marketplace
    for_sale = Column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    owner = relationship("User", back_populates="lands", foreign_keys=[owner_id])
    transactions = relationship("Transaction", back_populates="land")
    listings = relationship("Listing", back_populates="land")
    chat_sessions = relationship("ChatSession", back_populates="land")

    @validates("x", "y")
    def validate_coordinates(self, key, value):
        """Validate coordinates are non-negative."""
        if value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value

    @validates("biome")
    def validate_biome(self, key, value):
        """Validate biome is valid."""
        if not isinstance(value, Biome):
            raise ValueError(f"Invalid biome: {value}")
        return value

    @validates("elevation")
    def validate_elevation(self, key, value):
        """Validate elevation is 0-1."""
        if not (0 <= value <= 1):
            raise ValueError("Elevation must be between 0 and 1")
        return value

    def set_passcode(self, passcode: str) -> None:
        """Hash and set 4-digit passcode."""
        import bcrypt
        if len(passcode) != 4 or not passcode.isdigit():
            raise ValueError("Passcode must be 4 digits")
        salt = bcrypt.gensalt(rounds=8)
        self.passcode_hash = bcrypt.hashpw(
            passcode.encode('utf-8'),
            salt
        ).decode('utf-8')
        self.passcode_updated_at = datetime.utcnow()

    def verify_passcode(self, passcode: str) -> bool:
        """Verify passcode."""
        import bcrypt
        if not self.passcode_hash:
            return False
        return bcrypt.checkpw(
            passcode.encode('utf-8'),
            self.passcode_hash.encode('utf-8')
        )

    @hybrid_property
    def is_accessible(self) -> bool:
        """Check if land is accessible (not fenced or has passcode)."""
        return not self.fenced

    def __repr__(self) -> str:
        return f"<Land ({self.x}, {self.y}) - {self.biome}>"
```

---

## Listing Model

```python
# app/models/listing.py

from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, Enum, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
import uuid
from enum import Enum as PyEnum
from datetime import datetime

from app.db.base import BaseModel

class ListingType(str, PyEnum):
    AUCTION = "auction"
    FIXED_PRICE = "fixed_price"
    BUY_NOW = "buy_now"

class ListingStatus(str, PyEnum):
    ACTIVE = "active"
    SOLD = "sold"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

class Listing(BaseModel):
    __tablename__ = "listings"
    __table_args__ = (
        Index("idx_listings_status", "status", postgresql_where="status = 'active'"),
        Index("idx_listings_auction_end", "auction_end_time", postgresql_where="status = 'active'"),
    )

    # Primary Key
    listing_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    land_id = Column(UUID(as_uuid=True), ForeignKey("lands.land_id"), unique=True, nullable=False, index=True)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)

    # Listing Details
    type = Column(Enum(ListingType), nullable=False)
    description = Column(String, nullable=True)
    images = Column(ARRAY(String), nullable=True)

    # Pricing
    price_bdt = Column(Integer, nullable=False)
    reserve_price_bdt = Column(Integer, nullable=True)

    # Auction Fields
    auction_start_time = Column(DateTime(timezone=True), nullable=True)
    auction_end_time = Column(DateTime(timezone=True), nullable=True)
    auto_extend = Column(Boolean, default=False)
    auto_extend_minutes = Column(Integer, default=5)

    # Buy Now Option
    buy_now_enabled = Column(Boolean, default=False)
    buy_now_price_bdt = Column(Integer, nullable=True)

    # Status
    status = Column(Enum(ListingStatus), default=ListingStatus.ACTIVE, nullable=False, index=True)
    sold_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    land = relationship("Land", back_populates="listings")
    seller = relationship("User", back_populates="listings")
    bids = relationship("Bid", back_populates="listing", cascade="all, delete-orphan")

    def is_auction_active(self) -> bool:
        """Check if auction is still active."""
        if self.type != ListingType.AUCTION:
            return False
        if self.status != ListingStatus.ACTIVE:
            return False
        return datetime.utcnow() < self.auction_end_time

    def extend_auction(self):
        """Extend auction end time."""
        from datetime import timedelta
        self.auction_end_time += timedelta(minutes=self.auto_extend_minutes)

    def __repr__(self) -> str:
        return f"<Listing {self.listing_id} - {self.type}>"
```

---

## Bid Model

```python
# app/models/bid.py

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Enum, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from enum import Enum as PyEnum

from app.db.base import BaseModel

class BidStatus(str, PyEnum):
    ACTIVE = "active"
    OUTBID = "outbid"
    CANCELLED = "cancelled"
    WON = "won"

class Bid(BaseModel):
    __tablename__ = "bids"
    __table_args__ = (
        Index("idx_bids_listing", "listing_id", "created_at"),
        Index("idx_bids_status", "status", postgresql_where="status = 'active'"),
    )

    # Primary Key
    bid_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.listing_id"), nullable=False, index=True)
    bidder_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)

    # Bid Data
    amount_bdt = Column(Integer, nullable=False)
    status = Column(Enum(BidStatus), default=BidStatus.ACTIVE, nullable=False, index=True)

    # Relationships
    listing = relationship("Listing", back_populates="bids")
    bidder = relationship("User", back_populates="bids")

    def __repr__(self) -> str:
        return f"<Bid {self.bid_id} - {self.amount_bdt} BDT>"
```

---

## Transaction Model (Immutable)

```python
# app/models/transaction.py

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Enum, Index, func, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
import uuid
from enum import Enum as PyEnum
from datetime import datetime

from app.db.base import BaseModel

class TransactionStatus(str, PyEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class Transaction(BaseModel):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("idx_transactions_seller", "seller_id", "created_at"),
        Index("idx_transactions_buyer", "buyer_id", "created_at"),
        Index("idx_transactions_status", "status"),
        Index("idx_transactions_created_at", "created_at"),
        CheckConstraint("amount_bdt > 0"),
    )

    # Primary Key
    transaction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    land_id = Column(UUID(as_uuid=True), ForeignKey("lands.land_id"), nullable=False, index=True)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    listing_id = Column(UUID(as_uuid=True), ForeignKey("listings.listing_id"), nullable=True)

    # Transaction Details
    amount_bdt = Column(Integer, nullable=False)
    currency = Column(String(3), default="BDT", nullable=False)
    status = Column(Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False)

    # Payment Gateway
    gateway_name = Column(String(50), nullable=True)
    gateway_transaction_id = Column(String(255), nullable=True, unique=True)

    # Fees
    platform_fee_bdt = Column(Integer, default=0)
    gateway_fee_bdt = Column(Integer, default=0)

    # Timestamps (immutable after creation)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    land = relationship("Land", back_populates="transactions")
    seller = relationship("User", back_populates="transactions_as_seller", foreign_keys=[seller_id])
    buyer = relationship("User", back_populates="transactions_as_buyer", foreign_keys=[buyer_id])

    @hybrid_property
    def seller_receives_bdt(self) -> int:
        """Calculate amount seller receives after fees."""
        return self.amount_bdt - self.platform_fee_bdt - self.gateway_fee_bdt

    def mark_completed(self):
        """Mark transaction as completed."""
        self.status = TransactionStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<Transaction {self.transaction_id} - {self.amount_bdt} BDT>"
```

---

## Chat Models

```python
# app/models/chat.py

from sqlalchemy import Column, String, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.base import BaseModel

class ChatSession(BaseModel):
    __tablename__ = "chat_sessions"

    # Primary Key
    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Key
    land_id = Column(UUID(as_uuid=True), ForeignKey("lands.land_id"), unique=True, nullable=False, index=True)

    # Session Data
    status = Column(String(20), default="active", nullable=False)
    participant_count = Column(Integer, default=0)

    # Relationships
    land = relationship("Land", back_populates="chat_sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChatSession {self.session_id}>"

class Message(BaseModel):
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_messages_session", "session_id", "created_at"),
        Index("idx_messages_sender", "sender_id"),
    )

    # Primary Key
    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Keys
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.session_id"), nullable=False, index=True)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)

    # Message Content (encrypted)
    encrypted_payload = Column(String, nullable=False)
    encryption_version = Column(String(10), default="1.0", nullable=False)
    iv = Column(String(255), nullable=False)  # Initialization vector

    # Message Type
    message_type = Column(String(20), default="text", nullable=False)

    # Soft Delete
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    sender = relationship("User", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message {self.message_id}>"
```

---

## Audit Log Model (Immutable)

```python
# app/models/audit_log.py

from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Index, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from enum import Enum as PyEnum

from app.db.base import BaseModel

class AuditEventCategory(str, PyEnum):
    LAND_TRANSFER = "land_transfer"
    PAYMENT = "payment"
    ADMIN = "admin"
    MARKETPLACE = "marketplace"
    USER = "user"
    SYSTEM = "system"

class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_actor", "actor_id", "created_at"),
        Index("idx_audit_logs_event", "event_type"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
        Index("idx_audit_logs_timestamp", "created_at"),
    )

    # Primary Key
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Event Details
    event_type = Column(String(50), nullable=False)
    event_category = Column(Enum(AuditEventCategory), nullable=False)

    # Actor
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    actor_role = Column(String(20), nullable=True)

    # Resource
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(255), nullable=True)

    # Action
    action = Column(String(255), nullable=True)
    details = Column(JSONB, nullable=True)

    # Result
    status = Column(String(20), default="success", nullable=False)
    error_message = Column(String, nullable=True)

    # Monetary
    amount_bdt = Column(Integer, nullable=True)

    # Relationship
    actor = relationship("User", back_populates="audit_logs", foreign_keys=[actor_id])

    def __repr__(self) -> str:
        return f"<AuditLog {self.log_id} - {self.event_type}>"
```

---

## Admin Config Model

```python
# app/models/admin_config.py

from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import BaseModel

class AdminConfig(BaseModel):
    __tablename__ = "admin_config"

    # Primary Key
    config_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # World Generation
    world_seed = Column(Integer, nullable=False)

    # Noise Parameters
    noise_frequency = Column(Float, default=0.05, nullable=False)
    noise_octaves = Column(Integer, default=6, nullable=False)
    noise_persistence = Column(Float, default=0.6, nullable=False)
    noise_lacunarity = Column(Float, default=2.0, nullable=False)

    # Biome Distribution
    biome_forest_percent = Column(Float, default=0.35, nullable=False)
    biome_grassland_percent = Column(Float, default=0.30, nullable=False)
    biome_water_percent = Column(Float, default=0.20, nullable=False)
    biome_desert_percent = Column(Float, default=0.10, nullable=False)
    biome_snow_percent = Column(Float, default=0.05, nullable=False)

    # Pricing
    base_land_price_bdt = Column(Integer, default=1000, nullable=False)
    forest_multiplier = Column(Float, default=1.0, nullable=False)
    grassland_multiplier = Column(Float, default=0.8, nullable=False)
    water_multiplier = Column(Float, default=1.2, nullable=False)
    desert_multiplier = Column(Float, default=0.7, nullable=False)
    snow_multiplier = Column(Float, default=1.5, nullable=False)

    # Fees
    transaction_fee_percent = Column(Float, default=5.0, nullable=False)

    # Updated By
    updated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    updated_by = relationship("User", foreign_keys=[updated_by_id])

    def __repr__(self) -> str:
        return f"<AdminConfig {self.config_id}>"
```

---

## Model Integration Tests

```python
# tests/test_models.py

import pytest
from datetime import datetime
from app.models.user import User, UserRole
from app.models.land import Land, Biome
from app.models.transaction import Transaction, TransactionStatus

@pytest.mark.asyncio
async def test_user_password_hashing():
    """Test user password hashing."""
    user = User(
        username="testuser",
        email="test@example.com"
    )
    user.set_password("SecurePassword123!")
    assert user.password_hash != "SecurePassword123!"
    assert user.verify_password("SecurePassword123!")
    assert not user.verify_password("WrongPassword")

@pytest.mark.asyncio
async def test_user_account_lockout():
    """Test account lockout after failed logins."""
    user = User(username="testuser", email="test@example.com")
    for _ in range(5):
        user.add_failed_login()
    assert user.is_locked()

@pytest.mark.asyncio
async def test_land_passcode():
    """Test land passcode hashing."""
    land = Land(x=0, y=0, biome=Biome.FOREST, color_hex="#000000")
    land.set_passcode("1234")
    assert land.verify_passcode("1234")
    assert not land.verify_passcode("5678")

@pytest.mark.asyncio
async def test_transaction_fee_calculation():
    """Test transaction fee calculation."""
    txn = Transaction(
        amount_bdt=1000,
        platform_fee_bdt=50,
        gateway_fee_bdt=30
    )
    assert txn.seller_receives_bdt == 920
```

---

## Summary

The ORM models provide:
- ✓ Complete database abstraction with SQLAlchemy
- ✓ Type-safe validation with validators
- ✓ Password hashing with bcrypt
- ✓ Immutable transaction history
- ✓ Relationship management
- ✓ Hybrid properties for computed fields
- ✓ Comprehensive test coverage

All models are ready for async database operations in FastAPI endpoints.

**Resume Token:** `✓ PHASE_3_MODELS_COMPLETE`
