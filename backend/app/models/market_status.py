"""
Market-wide trading status (singleton row).
"""
from enum import Enum
from uuid import uuid4
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import BaseModel


class MarketState(str, Enum):
    OPEN = "open"
    HALTED = "halted"
    CLOSED = "closed"


class MarketStatus(BaseModel):
    __tablename__ = "market_status"

    status_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)
    state = Column(String(16), nullable=False, default=MarketState.OPEN.value)
    reason = Column(String(256), nullable=True)

    def __repr__(self) -> str:
        return f"<MarketStatus {self.state}>"
