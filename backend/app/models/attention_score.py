"""
AttentionScore model
Tracks user attention per biome for redistribution calculations
"""

from sqlalchemy import Column, Float, DateTime, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.base import BaseModel
from app.models.land import Biome


class AttentionScore(BaseModel):
    """
    Attention score tracking per user and biome.
    
    Accumulated during batch interval, used for redistribution calculations.
    Reset after each redistribution cycle.
    
    Attributes:
        score_id: Unique UUID identifier
        user_id: Reference to user
        biome: Biome type being tracked
        score: Accumulated attention score (clicks, views, time spent)
        last_activity: Timestamp of last activity
    """

    __tablename__ = "attention_scores"

    __table_args__ = (
        Index("idx_attention_scores_user_biome", "user_id", "biome", unique=True),
        Index("idx_attention_scores_biome", "biome"),
        Index("idx_attention_scores_updated", "updated_at"),
    )

    # Primary Key
    score_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Foreign Keys
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )

    biome = Column(
        SQLEnum(Biome),
        ForeignKey("biome_markets.biome"),
        nullable=False,
        index=True
    )

    # Score Data
    score = Column(
        Float,
        default=0.0,
        nullable=False
    )

    last_activity = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="attention_scores")
    biome_market = relationship("BiomeMarket")

    def add_score(self, amount: float) -> None:
        """
        Add to attention score.
        
        Args:
            amount: Score value to add
        """
        self.score += amount
        self.last_activity = datetime.utcnow()

    def reset(self) -> None:
        """Reset score after redistribution cycle."""
        self.score = 0.0

    def __repr__(self) -> str:
        """String representation of AttentionScore."""
        return f"<AttentionScore {self.user_id} - {self.biome.value}: {self.score}>"

    def to_dict(self) -> dict:
        """
        Convert attention score to dictionary for API responses.
        
        Returns:
            dict: Attention score data dictionary
        """
        return {
            "score_id": str(self.score_id),
            "user_id": str(self.user_id),
            "biome": self.biome.value,
            "score": self.score,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None
        }
