"""
Land Allocation Service
Automatically allocates land plots to new users with intelligent placement
"""

import random
import logging
from typing import List, Tuple, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from uuid import UUID

from app.models.land import Land, LandShape, Biome
from app.models.admin_config import AdminConfig
from app.models.user import User
from app.services.world_service import world_service

logger = logging.getLogger(__name__)


class LandAllocationService:
    """
    Handles automatic land allocation for new users.

    Features:
    - Weighted probability distribution for land sizes
    - Rare shape variations (circle, triangle, rectangle)
    - Intelligent adjacent placement algorithm
    - No-overlap validation with configurable buffer
    - Scalable spatial queries using database indexes
    """

    def __init__(self):
        """Initialize the land allocation service."""
        self.size_distribution = self._create_size_distribution()

    def _create_size_distribution(self) -> List[Tuple[int, float]]:
        """
        Create weighted size distribution.

        Returns:
            List of (size, probability) tuples

        Distribution:
        - 36x36: 60% probability
        - 63x63 to 75x75: 30% probability (distributed among 63, 69, 75)
        - 76x76 to 1000x1000: 10% probability (exponentially decreasing)
        """
        distribution = []

        # 36x36: 60% probability
        distribution.append((36, 0.60))

        # Medium sizes (63-75): 30% total
        medium_sizes = [63, 69, 75]
        medium_prob = 0.30 / len(medium_sizes)
        for size in medium_sizes:
            distribution.append((size, medium_prob))

        # Large sizes (76-1000): 10% total, exponentially decreasing
        # Use exponential decay for rarity
        large_sizes = [100, 150, 200, 300, 500, 750, 1000]
        total_large_prob = 0.10

        # Exponential decay weights
        decay_factor = 0.5
        weights = [decay_factor ** i for i in range(len(large_sizes))]
        total_weight = sum(weights)

        for size, weight in zip(large_sizes, weights):
            prob = (weight / total_weight) * total_large_prob
            distribution.append((size, prob))

        # Normalize probabilities (should sum to ~1.0)
        total_prob = sum(p for _, p in distribution)
        distribution = [(s, p/total_prob) for s, p in distribution]

        logger.info(f"Created size distribution with {len(distribution)} size categories")
        return distribution

    def _select_land_size(self) -> int:
        """
        Select land size using weighted random selection.

        Returns:
            Selected land size (width/height for square)
        """
        sizes, probabilities = zip(*self.size_distribution)
        selected_size = random.choices(sizes, weights=probabilities, k=1)[0]
        logger.debug(f"Selected land size: {selected_size}x{selected_size}")
        return selected_size

    def _select_land_shape(self, config: AdminConfig) -> LandShape:
        """
        Select land shape with rare variation.

        Args:
            config: Admin configuration

        Returns:
            Selected land shape

        Distribution:
        - Square: 95%
        - Other shapes (circle/triangle/rectangle): 5% combined
        """
        if not config.starter_shape_variation_enabled:
            return LandShape.SQUARE

        # 95% square, 5% other shapes
        if random.random() < 0.95:
            return LandShape.SQUARE

        # Randomly select from other shapes
        other_shapes = [LandShape.CIRCLE, LandShape.TRIANGLE, LandShape.RECTANGLE]
        selected = random.choice(other_shapes)
        logger.debug(f"Selected rare shape: {selected.value}")
        return selected

    async def _find_adjacent_position(
        self,
        db: AsyncSession,
        width: int,
        height: int,
        buffer: int,
        max_attempts: int = 100
    ) -> Optional[Tuple[int, int]]:
        """
        Find an available position adjacent to existing lands.

        Strategy:
        1. Query existing lands to find occupied regions
        2. Identify frontier (edges of occupied regions)
        3. Try to place new land adjacent to frontier
        4. Validate no overlap with buffer

        Args:
            db: Database session
            width: Land width
            height: Land height
            buffer: Buffer distance in units
            max_attempts: Maximum placement attempts

        Returns:
            (x, y) coordinates if found, None otherwise
        """
        # Get count of existing lands
        result = await db.execute(select(func.count(Land.land_id)))
        land_count = result.scalar()

        # If no lands exist, start at origin
        if land_count == 0:
            logger.info("No existing lands, placing at origin (0, 0)")
            return (0, 0)

        # Find the bounding box of all existing lands
        result = await db.execute(
            select(
                func.min(Land.x).label('min_x'),
                func.max(Land.x + Land.width).label('max_x'),
                func.min(Land.y).label('min_y'),
                func.max(Land.y + Land.height).label('max_y')
            )
        )
        bounds = result.one()

        # Expand search area slightly beyond bounds
        search_min_x = bounds.min_x - width - buffer * 10
        search_max_x = bounds.max_x + buffer * 10
        search_min_y = bounds.min_y - height - buffer * 10
        search_max_y = bounds.max_y + buffer * 10

        logger.debug(f"Search area: x[{search_min_x}, {search_max_x}], y[{search_min_y}, {search_max_y}]")

        # Try random positions near existing lands
        for attempt in range(max_attempts):
            # Generate candidate position
            if attempt < max_attempts // 2:
                # First half: try positions near existing land boundaries
                # Only use negative x if min_x would still be >= 0
                if bounds.min_x - width - buffer >= 0:
                    x = random.choice([bounds.min_x - width - buffer, bounds.max_x + buffer])
                else:
                    x = bounds.max_x + buffer
                y = random.randint(max(0, int(bounds.min_y)), int(bounds.max_y))
            else:
                # Second half: try random positions in search area (ensure non-negative)
                x = random.randint(max(0, int(search_min_x)), int(search_max_x))
                y = random.randint(max(0, int(search_min_y)), int(search_max_y))

            # Validate position
            if await self._is_position_valid(db, x, y, width, height, buffer):
                logger.info(f"Found valid position at ({x}, {y}) after {attempt + 1} attempts")
                return (x, y)

        logger.warning(f"Failed to find valid position after {max_attempts} attempts")
        return None

    async def _is_position_valid(
        self,
        db: AsyncSession,
        x: int,
        y: int,
        width: int,
        height: int,
        buffer: int
    ) -> bool:
        """
        Check if a position is valid (no overlap with buffer).

        Args:
            db: Database session
            x, y: Candidate position
            width, height: Land dimensions
            buffer: Buffer distance

        Returns:
            True if valid, False if overlaps
        """
        # Calculate bounding box with buffer
        check_x_min = x - buffer
        check_x_max = x + width + buffer
        check_y_min = y - buffer
        check_y_max = y + height + buffer

        # Query for any overlapping lands
        result = await db.execute(
            select(func.count(Land.land_id))
            .where(
                and_(
                    # Check for overlap using bounding box intersection
                    Land.x < check_x_max,
                    Land.x + Land.width > check_x_min,
                    Land.y < check_y_max,
                    Land.y + Land.height > check_y_min
                )
            )
        )

        overlap_count = result.scalar()
        return overlap_count == 0

    async def allocate_starter_land(
        self,
        db: AsyncSession,
        user: User
    ) -> Optional[List[Land]]:
        """
        Allocate starter land plot to a new user.

        Args:
            db: Database session
            user: User to allocate land to

        Returns:
            List of created Land objects, or None if allocation failed

        Process:
        1. Load admin configuration
        2. Select size and shape
        3. Find valid adjacent position
        4. Generate land records using world generation
        5. Create land ownership records
        """
        # Check if starter land is enabled
        result = await db.execute(select(AdminConfig))
        config = result.scalar_one_or_none()

        if not config or not config.starter_land_enabled:
            logger.info("Starter land allocation is disabled")
            return None

        # Select size and shape
        size = self._select_land_size()
        shape = self._select_land_shape(config)

        # Clamp size to configured limits
        size = max(config.starter_land_min_size, min(size, config.starter_land_max_size))

        # For non-square shapes, adjust dimensions
        width, height = self._get_shape_dimensions(size, shape)

        logger.info(f"Allocating {shape.value} land {width}x{height} to user {user.username}")

        # Find adjacent position
        position = await self._find_adjacent_position(
            db,
            width,
            height,
            config.starter_land_buffer_units
        )

        if not position:
            logger.error(f"Failed to find position for user {user.username}")
            return None

        start_x, start_y = position

        # Create land records for the allocated plot
        lands = []

        for local_y in range(height):
            for local_x in range(width):
                world_x = start_x + local_x
                world_y = start_y + local_y

                # Get world generation data for this position
                land_data = world_service.get_land_at(world_x, world_y)

                # Create land record
                land = Land(
                    owner_id=user.user_id,
                    x=world_x,
                    y=world_y,
                    z=0,
                    biome=Biome(land_data['biome']),
                    elevation=land_data['elevation'],
                    color_hex=self._get_color_for_biome(land_data['biome']),
                    shape=shape,
                    width=1,  # Individual unit width
                    height=1,  # Individual unit height
                    price_base_bdt=land_data['base_price_bdt']
                )

                lands.append(land)

        # Bulk insert lands
        db.add_all(lands)
        await db.commit()
        
        # Create a transaction record for starter allocation (zero-amount)
        try:
            from app.models.transaction import Transaction, TransactionType, TransactionStatus
            primary_land_id = lands[0].land_id if lands else None
            allocation_txn = Transaction(
                land_id=primary_land_id,
                buyer_id=user.user_id,
                seller_id=None,
                listing_id=None,
                transaction_type=TransactionType.TRANSFER,
                amount_bdt=0,
                currency="BDT",
                status=TransactionStatus.COMPLETED,
                platform_fee_bdt=0,
                gateway_fee_bdt=0,
                gateway_name="STARTER_ALLOCATION"
            )
            db.add(allocation_txn)
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to record starter allocation transaction: {e}")

        logger.info(f"Allocated {len(lands)} land units to user {user.username} at ({start_x}, {start_y})")

        return lands

    def _get_shape_dimensions(self, size: int, shape: LandShape) -> Tuple[int, int]:
        """
        Calculate width and height based on size and shape.

        Args:
            size: Base size
            shape: Land shape

        Returns:
            (width, height) tuple
        """
        if shape == LandShape.SQUARE:
            return (size, size)
        elif shape == LandShape.CIRCLE:
            # Circle inscribed in square
            return (size, size)
        elif shape == LandShape.TRIANGLE:
            # Isosceles triangle
            return (size, int(size * 0.866))  # height ≈ base * √3/2
        elif shape == LandShape.RECTANGLE:
            # Random aspect ratio (1.5:1 or 2:1)
            if random.random() < 0.5:
                return (size, int(size * 0.67))  # 1.5:1
            else:
                return (size, int(size * 0.5))   # 2:1
        else:
            return (size, size)

    def _get_color_for_biome(self, biome: str) -> str:
        """
        Get hex color for biome.

        Args:
            biome: Biome name

        Returns:
            Hex color string
        """
        colors = {
            "ocean": "#1A5490",
            "beach": "#e8bd88",
            "plains": "#7ba62a",
            "forest": "#2d5016",
            "desert": "#d4a26e",
            "mountain": "#6b7280",
            "snow": "#f0f0f0"
        }
        return colors.get(biome, "#7ba62a")


# Global instance
land_allocation_service = LandAllocationService()
