"""
Database base configuration and mixins
Provides base model class with common timestamp fields
"""

from sqlalchemy import Column, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime


# Base class for all ORM models
Base = declarative_base()


class TimestampMixin:
    """Mixin to add timestamp columns to models."""

    created_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
        index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    def soft_delete(self):
        """Soft delete the record by setting deleted_at timestamp."""
        self.deleted_at = datetime.utcnow()

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted."""
        return self.deleted_at is not None


class BaseModel(Base):
    """Abstract base model with timestamp fields."""

    __abstract__ = True

    created_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        nullable=False,
        index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
