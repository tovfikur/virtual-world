"""
Attention Tracking Service
Tracks user attention per biome for market redistribution
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Optional
import uuid
import logging

from app.models.attention_score import AttentionScore
from app.models.land import Biome
from app.models.user import User

logger = logging.getLogger(__name__)


class AttentionTrackingService:
    """Service for tracking user attention across biomes."""

    @staticmethod
    async def track_attention(
        db: AsyncSession,
        user_id: uuid.UUID,
        biome: Biome,
        score: float
    ) -> AttentionScore:
        """
        Track user attention for a biome.
        
        Args:
            db: Database session
            user_id: User ID
            biome: Biome type
            score: Attention score to add
            
        Returns:
            AttentionScore record
        """
        # Get or create attention score record
        result = await db.execute(
            select(AttentionScore).where(
                AttentionScore.user_id == user_id,
                AttentionScore.biome == biome
            )
        )
        attention_score = result.scalar_one_or_none()

        if not attention_score:
            attention_score = AttentionScore(
                user_id=user_id,
                biome=biome,
                score=0.0
            )
            db.add(attention_score)

        # Add score
        attention_score.add_score(score)
        
        await db.commit()
        await db.refresh(attention_score)

        logger.debug(f"Tracked attention: user={user_id}, biome={biome.value}, score={score}")

        return attention_score

    @staticmethod
    async def get_user_attention(
        db: AsyncSession,
        user_id: uuid.UUID,
        biome: Optional[Biome] = None
    ) -> list:
        """
        Get user's attention scores.
        
        Args:
            db: Database session
            user_id: User ID
            biome: Optional biome filter
            
        Returns:
            List of AttentionScore records
        """
        query = select(AttentionScore).where(AttentionScore.user_id == user_id)
        
        if biome:
            query = query.where(AttentionScore.biome == biome)

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_biome_total_attention(
        db: AsyncSession,
        biome: Biome
    ) -> float:
        """
        Get total attention score for a biome across all users.
        
        Args:
            db: Database session
            biome: Biome type
            
        Returns:
            Total attention score
        """
        from sqlalchemy import func
        
        result = await db.execute(
            select(func.sum(AttentionScore.score)).where(
                AttentionScore.biome == biome
            )
        )
        total = result.scalar()
        return total if total else 0.0

    @staticmethod
    async def reset_all_attention(db: AsyncSession) -> None:
        """
        Reset all attention scores to zero.
        Called after redistribution cycle.
        
        Args:
            db: Database session
        """
        result = await db.execute(select(AttentionScore))
        attention_scores = result.scalars().all()

        for score in attention_scores:
            score.reset()

        await db.commit()
        logger.info("Reset all attention scores")


# Global instance
attention_tracking_service = AttentionTrackingService()
