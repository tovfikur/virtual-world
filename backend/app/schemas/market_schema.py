from enum import Enum
from pydantic import BaseModel, Field


class MarketState(str, Enum):
    OPEN = "open"
    HALTED = "halted"
    CLOSED = "closed"


class MarketStatusOut(BaseModel):
    state: MarketState
    reason: str | None = None


class MarketStatusUpdate(BaseModel):
    state: MarketState = Field(..., description="open/halted/closed")
    reason: str | None = Field(None, max_length=256)
