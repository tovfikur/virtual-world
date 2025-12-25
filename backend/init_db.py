"""
Initialize Database with Default Admin User and Config
Run this script after database setup to create default admin and config.
"""

import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import uuid

from app.config import settings
from app.models.admin_config import AdminConfig
from app.models.user import User, UserRole


async def create_default_admin():
    """Create default admin user if it doesn't exist."""

    environment = (settings.environment or "development").lower()
    create_demo_admin = os.getenv("CREATE_DEMO_ADMIN", "").lower() in ("1", "true", "yes")

    # In non-production, default to creating a demo admin unless explicitly disabled.
    if environment != "production" and os.getenv("CREATE_DEMO_ADMIN") is None:
        create_demo_admin = True

    bootstrap_email = (os.getenv("ADMIN_BOOTSTRAP_EMAIL") or "").strip()
    bootstrap_password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD") or ""
    demo_email = (os.getenv("DEMO_ADMIN_EMAIL") or "demo@example.com").strip()
    demo_password = os.getenv("DEMO_ADMIN_PASSWORD") or "DemoPassword123!"

    # Create async engine
    engine = create_async_engine(str(settings.database_url), echo=False)

    # Create all tables from models (SQLAlchemy-based schema initialization)
    from app.db.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create async session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        admin_user = None

        if environment == "production":
            if not bootstrap_email or not bootstrap_password:
                raise RuntimeError(
                    "Production bootstrap requires ADMIN_BOOTSTRAP_EMAIL and ADMIN_BOOTSTRAP_PASSWORD. "
                    "Set these env vars (or run init_db manually in a secure environment)."
                )

            # Find existing bootstrap admin by email
            result = await session.execute(select(User).where(User.email == bootstrap_email))
            existing_admin = result.scalar_one_or_none()

            if existing_admin:
                admin_user = existing_admin
                print(f"✓ Admin user already exists ({bootstrap_email})")
            else:
                admin_user = User(
                    user_id=uuid.uuid4(),
                    username="admin",
                    email=bootstrap_email,
                    role=UserRole.ADMIN,
                    verified=True,
                    balance_bdt=0,
                )
                admin_user.set_password(bootstrap_password)
                session.add(admin_user)
                await session.commit()
                await session.refresh(admin_user)
                print(f"✓ Admin user created successfully ({bootstrap_email})")

        else:
            if create_demo_admin:
                result = await session.execute(select(User).where(User.email == demo_email))
                existing_admin = result.scalar_one_or_none()

                if existing_admin:
                    admin_user = existing_admin
                    print(f"✓ Demo admin user already exists ({demo_email})")
                else:
                    admin_user = User(
                        user_id=uuid.uuid4(),
                        username="admin",
                        email=demo_email,
                        role=UserRole.ADMIN,
                        verified=True,
                        balance_bdt=0,
                    )
                    admin_user.set_password(demo_password)
                    session.add(admin_user)
                    await session.commit()
                    await session.refresh(admin_user)

                    print("✓ Demo admin user created successfully!")
                    print(f"  - Email: {demo_email}")
                    print(f"  - Password: {demo_password}")
                    print("  - Role: ADMIN")
            else:
                print("ℹ️  CREATE_DEMO_ADMIN is disabled; no admin user will be created")

        # Admin config requires an admin reference
        if not admin_user:
            raise RuntimeError(
                "AdminConfig requires an admin user (updated_by_id). "
                "Enable demo admin (CREATE_DEMO_ADMIN=true) or set ADMIN_BOOTSTRAP_EMAIL/ADMIN_BOOTSTRAP_PASSWORD."
            )

        # Check if admin config exists
        result = await session.execute(select(AdminConfig))
        existing_config = result.scalar_one_or_none()

        if existing_config:
            print("✓ Admin config already exists")
        else:
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
                updated_by_id=admin_user.user_id
            )

            session.add(config)
            await session.commit()

            print("✓ Admin config created successfully!")
            print(f"  - World seed: {config.world_seed}")
            print(f"  - Starter land enabled: {config.starter_land_enabled}")
            print(f"  - Land size range: {config.starter_land_min_size}x{config.starter_land_min_size} to {config.starter_land_max_size}x{config.starter_land_max_size}")

    await engine.dispose()


async def main():
    """Main initialization function."""
    print("=" * 60)
    print("Database Initialization Script")
    print("=" * 60)
    print()

    try:
        await create_default_admin()
        print()
        print("=" * 60)
        print("✓ Database initialization completed successfully!")
        print("=" * 60)
        print()
        print("Default Admin Credentials:")
        print("  Email:    demo@example.com")
        print("  Password: DemoPassword123!")
        print()
        print("Admin Panel: http://localhost/admin")
        print("=" * 60)
        return 0
    except Exception as e:
        print()
        print("=" * 60)
        print("✗ Database initialization failed!")
        print("=" * 60)
        print(f"Error: {str(e)}")
        print()
        print("Make sure:")
        print("  1. Database is running (docker-compose up -d postgres)")
        print("  2. Migrations are applied (alembic upgrade head)")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
