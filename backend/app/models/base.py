"""
Base model imports and exports.
Re-exports from db.base for convenience.
"""

from app.db.base import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]
