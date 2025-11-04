"""
Tests for Land Allocation Service
"""

import pytest
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from collections import Counter

from app.models.user import User
from app.models.land import Land, LandShape
from app.models.admin_config import AdminConfig
from app.services.land_allocation_service import land_allocation_service
from app.db.base import Base


# Test database URL (use in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create test database and session."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def admin_config(test_db: AsyncSession):
    """Create admin config for testing."""
    # Create a test admin user first
    admin = User(
        username="admin",
        email="admin@test.com"
    )
    admin.set_password("AdminPassword123!")

    test_db.add(admin)
    await test_db.commit()
    await test_db.refresh(admin)

    # Create config
    config = AdminConfig(
        world_seed=12345,
        noise_frequency=0.05,
        noise_octaves=6,
        noise_persistence=0.6,
        noise_lacunarity=2.0,
        biome_forest_percent=0.35,
        biome_grassland_percent=0.30,
        biome_water_percent=0.20,
        biome_desert_percent=0.10,
        biome_snow_percent=0.05,
        base_land_price_bdt=1000,
        forest_multiplier=1.0,
        grassland_multiplier=0.8,
        water_multiplier=1.2,
        desert_multiplier=0.7,
        snow_multiplier=1.5,
        transaction_fee_percent=5.0,
        starter_land_enabled=True,
        starter_land_min_size=36,
        starter_land_max_size=1000,
        starter_land_buffer_units=1,
        starter_shape_variation_enabled=True,
        updated_by_id=admin.user_id
    )

    test_db.add(config)
    await test_db.commit()
    await test_db.refresh(config)

    return config


@pytest.fixture
async def test_user(test_db: AsyncSession):
    """Create test user."""
    user = User(
        username="testuser",
        email="test@example.com"
    )
    user.set_password("TestPassword123!")

    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)

    return user


class TestSizeDistribution:
    """Test land size probability distribution."""

    @pytest.mark.asyncio
    async def test_size_selection_distribution(self):
        """Test that size selection follows the expected probability distribution."""
        # Run many iterations to test statistical distribution
        iterations = 10000
        sizes = [land_allocation_service._select_land_size() for _ in range(iterations)]

        size_counts = Counter(sizes)

        # Check 36x36 appears around 60% of the time (±5% tolerance)
        freq_36 = size_counts[36] / iterations
        assert 0.55 <= freq_36 <= 0.65, f"36x36 frequency {freq_36} outside expected range"

        # Check medium sizes (63, 69, 75) appear around 30% combined
        freq_medium = (size_counts[63] + size_counts[69] + size_counts[75]) / iterations
        assert 0.25 <= freq_medium <= 0.35, f"Medium size frequency {freq_medium} outside expected range"

        # Check large sizes (100+) appear around 10% combined
        large_sizes = [100, 150, 200, 300, 500, 750, 1000]
        freq_large = sum(size_counts.get(s, 0) for s in large_sizes) / iterations
        assert 0.05 <= freq_large <= 0.15, f"Large size frequency {freq_large} outside expected range"

    @pytest.mark.asyncio
    async def test_largest_sizes_are_rarest(self):
        """Test that 1000x1000 is rarer than 100x100."""
        iterations = 10000
        sizes = [land_allocation_service._select_land_size() for _ in range(iterations)]

        size_counts = Counter(sizes)

        # 100x100 should be more common than 1000x1000
        assert size_counts.get(100, 0) > size_counts.get(1000, 0)


class TestShapeDistribution:
    """Test land shape probability distribution."""

    @pytest.mark.asyncio
    async def test_shape_selection_distribution(self, admin_config: AdminConfig):
        """Test that shape selection is ~95% square."""
        iterations = 1000
        shapes = [land_allocation_service._select_land_shape(admin_config) for _ in range(iterations)]

        shape_counts = Counter(shapes)

        # Check squares are ~95% (±5% tolerance)
        freq_square = shape_counts[LandShape.SQUARE] / iterations
        assert 0.90 <= freq_square <= 1.0, f"Square frequency {freq_square} outside expected range"

        # Check non-square shapes are ~5% combined
        freq_non_square = 1 - freq_square
        assert 0.0 <= freq_non_square <= 0.10, f"Non-square frequency {freq_non_square} outside expected range"

    @pytest.mark.asyncio
    async def test_shape_variation_can_be_disabled(self, admin_config: AdminConfig):
        """Test that disabling shape variation always returns square."""
        admin_config.starter_shape_variation_enabled = False

        for _ in range(100):
            shape = land_allocation_service._select_land_shape(admin_config)
            assert shape == LandShape.SQUARE


class TestPlacementAlgorithm:
    """Test land placement and adjacency logic."""

    @pytest.mark.asyncio
    async def test_first_land_at_origin(self, test_db: AsyncSession, test_user: User, admin_config: AdminConfig):
        """Test that first land is placed at origin."""
        position = await land_allocation_service._find_adjacent_position(
            test_db,
            width=36,
            height=36,
            buffer=1
        )

        assert position is not None
        assert position == (0, 0)

    @pytest.mark.asyncio
    async def test_no_overlap_validation(self, test_db: AsyncSession, test_user: User, admin_config: AdminConfig):
        """Test that overlap detection works correctly."""
        # Create existing land at (0, 0) with size 10x10
        existing_land = Land(
            owner_id=test_user.user_id,
            x=0,
            y=0,
            z=0,
            biome="plains",
            elevation=0.5,
            color_hex="#7ba62a",
            shape=LandShape.SQUARE,
            width=10,
            height=10,
            price_base_bdt=1000
        )

        test_db.add(existing_land)
        await test_db.commit()

        # Test overlapping position (should be invalid)
        is_valid = await land_allocation_service._is_position_valid(
            test_db,
            x=5,
            y=5,
            width=10,
            height=10,
            buffer=1
        )

        assert not is_valid, "Overlapping position should be invalid"

    @pytest.mark.asyncio
    async def test_buffer_spacing(self, test_db: AsyncSession, test_user: User, admin_config: AdminConfig):
        """Test that buffer spacing is enforced."""
        # Create existing land at (0, 0) with size 10x10
        existing_land = Land(
            owner_id=test_user.user_id,
            x=0,
            y=0,
            z=0,
            biome="plains",
            elevation=0.5,
            color_hex="#7ba62a",
            shape=LandShape.SQUARE,
            width=10,
            height=10,
            price_base_bdt=1000
        )

        test_db.add(existing_land)
        await test_db.commit()

        # Position at (10, 0) with buffer=1 should be invalid (too close)
        is_valid = await land_allocation_service._is_position_valid(
            test_db,
            x=10,
            y=0,
            width=10,
            height=10,
            buffer=1
        )

        assert not is_valid, "Position within buffer should be invalid"

        # Position at (11, 0) with buffer=1 should be valid (respects buffer)
        is_valid = await land_allocation_service._is_position_valid(
            test_db,
            x=11,
            y=0,
            width=10,
            height=10,
            buffer=1
        )

        assert is_valid, "Position outside buffer should be valid"

    @pytest.mark.asyncio
    async def test_adjacent_placement(self, test_db: AsyncSession, test_user: User, admin_config: AdminConfig):
        """Test that new lands are placed adjacent to existing ones."""
        # Create existing land
        existing_land = Land(
            owner_id=test_user.user_id,
            x=0,
            y=0,
            z=0,
            biome="plains",
            elevation=0.5,
            color_hex="#7ba62a",
            shape=LandShape.SQUARE,
            width=50,
            height=50,
            price_base_bdt=1000
        )

        test_db.add(existing_land)
        await test_db.commit()

        # Find position for new land
        position = await land_allocation_service._find_adjacent_position(
            test_db,
            width=36,
            height=36,
            buffer=1,
            max_attempts=100
        )

        assert position is not None, "Should find adjacent position"

        x, y = position

        # Verify position is adjacent (within reasonable distance)
        # Should be near the existing land bounds
        distance_from_origin = max(abs(x), abs(y))
        assert distance_from_origin < 200, f"Position {position} too far from existing land"


class TestEndToEndAllocation:
    """End-to-end tests for complete land allocation flow."""

    @pytest.mark.asyncio
    async def test_allocate_starter_land(self, test_db: AsyncSession, test_user: User, admin_config: AdminConfig):
        """Test complete land allocation process."""
        lands = await land_allocation_service.allocate_starter_land(test_db, test_user)

        assert lands is not None, "Land allocation should succeed"
        assert len(lands) > 0, "Should allocate at least one land unit"

        # Verify all lands belong to user
        for land in lands:
            assert land.owner_id == test_user.user_id

        # Verify lands have valid properties
        for land in lands:
            assert land.x >= 0
            assert land.y >= 0
            assert land.biome is not None
            assert land.shape is not None
            assert land.width >= 1
            assert land.height >= 1

    @pytest.mark.asyncio
    async def test_multiple_users_allocation(self, test_db: AsyncSession, admin_config: AdminConfig):
        """Test that multiple users can be allocated land without conflicts."""
        users = []

        # Create multiple test users
        for i in range(5):
            user = User(
                username=f"user{i}",
                email=f"user{i}@test.com"
            )
            user.set_password("Password123!")
            test_db.add(user)
            users.append(user)

        await test_db.commit()

        # Allocate land to each user
        for user in users:
            await test_db.refresh(user)
            lands = await land_allocation_service.allocate_starter_land(test_db, user)
            assert lands is not None, f"Allocation failed for {user.username}"
            assert len(lands) > 0

        # Verify no overlaps exist
        from sqlalchemy import select, func

        result = await test_db.execute(select(func.count(Land.land_id)))
        total_lands = result.scalar()

        # Count distinct coordinates
        result = await test_db.execute(
            select(func.count(func.distinct(Land.x * 1000000 + Land.y)))
        )
        distinct_coords = result.scalar()

        assert total_lands == distinct_coords, "Overlapping lands detected"

    @pytest.mark.asyncio
    async def test_disabled_allocation(self, test_db: AsyncSession, test_user: User, admin_config: AdminConfig):
        """Test that allocation can be disabled via config."""
        admin_config.starter_land_enabled = False
        await test_db.commit()

        lands = await land_allocation_service.allocate_starter_land(test_db, test_user)

        assert lands is None, "Allocation should return None when disabled"


class TestShapeDimensions:
    """Test shape dimension calculations."""

    def test_square_dimensions(self):
        """Test square shape dimensions."""
        width, height = land_allocation_service._get_shape_dimensions(100, LandShape.SQUARE)
        assert width == 100
        assert height == 100

    def test_circle_dimensions(self):
        """Test circle shape dimensions (inscribed in square)."""
        width, height = land_allocation_service._get_shape_dimensions(100, LandShape.CIRCLE)
        assert width == 100
        assert height == 100

    def test_triangle_dimensions(self):
        """Test triangle shape dimensions."""
        width, height = land_allocation_service._get_shape_dimensions(100, LandShape.TRIANGLE)
        assert width == 100
        assert 80 <= height <= 90  # Approximately √3/2 * base

    def test_rectangle_dimensions(self):
        """Test rectangle shape dimensions."""
        width, height = land_allocation_service._get_shape_dimensions(100, LandShape.RECTANGLE)
        assert width == 100
        assert height in [50, 67]  # Either 2:1 or 1.5:1 aspect ratio


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
