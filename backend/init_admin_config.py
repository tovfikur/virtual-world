"""
Initialize Admin Config
Run this script to create default admin configuration for the system.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import uuid

from app.config import settings
from app.models.admin_config import AdminConfig
from app.models.user import User


async def init_admin_config():
    """Initialize admin config with default values."""

    # Create async engine
    engine = create_async_engine(str(settings.database_url), echo=True)

    # Create async session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Check if config already exists
        result = await session.execute(select(AdminConfig))
        existing_config = result.scalar_one_or_none()

        if existing_config:
            print("✓ Admin config already exists")
            return

        # Get first user for updated_by field (or create system user)
        result = await session.execute(select(User).limit(1))
        first_user = result.scalar_one_or_none()

        if not first_user:
            print("✗ No users found. Please create at least one user first.")
            return

        # Create default admin config
        config = AdminConfig(
            config_id=uuid.uuid4(),
            world_seed=12345,

            # Noise parameters
            noise_frequency=0.05,
            noise_octaves=6,
            noise_persistence=0.6,
            noise_lacunarity=2.0,

            # Biome distribution (must sum to 1.0)
            biome_forest_percent=0.2,
            biome_grassland_percent=0.2,
            biome_water_percent=0.2,
            biome_desert_percent=0.2,
            biome_snow_percent=0.2,

            # Pricing
            base_land_price_bdt=1000,
            forest_multiplier=1.0,
            grassland_multiplier=0.8,
            water_multiplier=1.2,
            desert_multiplier=0.7,
            snow_multiplier=1.5,

            # Fees
            transaction_fee_percent=5.0,

            # Land allocation settings
            starter_land_enabled=True,
            starter_land_min_size=36,
            starter_land_max_size=1000,
            starter_land_buffer_units=1,
            starter_shape_variation_enabled=True,

            # Meta
            updated_by_id=first_user.user_id
        )

        session.add(config)
        await session.commit()

        print("✓ Admin config created successfully!")
        print(f"  - World seed: {config.world_seed}")
        print(f"  - Starter land enabled: {config.starter_land_enabled}")
        print(f"  - Min/Max land size: {config.starter_land_min_size}x{config.starter_land_min_size} to {config.starter_land_max_size}x{config.starter_land_max_size}")

    await engine.dispose()


if __name__ == "__main__":
    print("Initializing admin configuration...")
    asyncio.run(init_admin_config())
    print("Done!")
