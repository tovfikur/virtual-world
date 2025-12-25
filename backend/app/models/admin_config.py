"""
Admin Config model
World generation and platform configuration
"""

from sqlalchemy import Column, Integer, Float, ForeignKey, CheckConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import BaseModel


class AdminConfig(BaseModel):
    """
    Admin configuration for world generation and pricing.

    Only one record should exist (singleton pattern).
    Updated by admins to control world generation and economics.

    Attributes:
        config_id: Unique UUID identifier
        world_seed: Seed for deterministic world generation
        noise_frequency: OpenSimplex noise frequency
        noise_octaves: Number of noise layers
        noise_persistence: Amplitude falloff per octave
        noise_lacunarity: Frequency multiplier per octave
        biome_*_percent: Distribution percentages (must sum to 1.0)
        base_land_price_bdt: Base price per land triangle
        *_multiplier: Price multipliers per biome
        transaction_fee_percent: Platform commission percentage
        updated_by_id: Admin who last updated config
    """

    __tablename__ = "admin_config"

    __table_args__ = (
        CheckConstraint(
            "noise_octaves >= 1 AND noise_octaves <= 8",
            name="check_octaves_range"
        ),
        CheckConstraint(
            "noise_persistence > 0 AND noise_persistence < 1",
            name="check_persistence_range"
        ),
        CheckConstraint(
            "noise_lacunarity > 1",
            name="check_lacunarity_range"
        ),
        CheckConstraint(
            "biome_forest_percent + biome_grassland_percent + biome_water_percent + "
            "biome_desert_percent + biome_snow_percent = 1.0",
            name="check_biome_distribution_sum"
        ),
        CheckConstraint(
            "transaction_fee_percent >= 0 AND transaction_fee_percent <= 100",
            name="check_fee_percentage"
        ),
    )

    # Primary Key
    config_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # World Generation Parameters
    world_seed = Column(
        Integer,
        nullable=False,
        default=12345
    )

    # Noise Parameters (OpenSimplex)
    noise_frequency = Column(
        Float,
        default=0.05,
        nullable=False
    )
    noise_octaves = Column(
        Integer,
        default=6,
        nullable=False
    )
    noise_persistence = Column(
        Float,
        default=0.6,
        nullable=False
    )
    noise_lacunarity = Column(
        Float,
        default=2.0,
        nullable=False
    )

    # Biome Distribution (percentages, must sum to 1.0)
    biome_forest_percent = Column(
        Float,
        default=0.35,
        nullable=False
    )
    biome_grassland_percent = Column(
        Float,
        default=0.30,
        nullable=False
    )
    biome_water_percent = Column(
        Float,
        default=0.20,
        nullable=False
    )
    biome_desert_percent = Column(
        Float,
        default=0.10,
        nullable=False
    )
    biome_snow_percent = Column(
        Float,
        default=0.05,
        nullable=False
    )

    # Pricing Configuration
    base_land_price_bdt = Column(
        Integer,
        default=1000,
        nullable=False
    )
    forest_multiplier = Column(
        Float,
        default=1.0,
        nullable=False
    )
    grassland_multiplier = Column(
        Float,
        default=0.8,
        nullable=False
    )
    water_multiplier = Column(
        Float,
        default=1.2,
        nullable=False
    )
    desert_multiplier = Column(
        Float,
        default=0.7,
        nullable=False
    )
    snow_multiplier = Column(
        Float,
        default=1.5,
        nullable=False
    )

    # Platform Fees
    transaction_fee_percent = Column(
        Float,
        default=5.0,
        nullable=False
    )
    biome_trade_fee_percent = Column(
        Float,
        default=2.0,
        nullable=False,
        comment="Platform fee for biome share trading (separate from marketplace)"
    )

    # Biome Market Controls
    max_price_move_percent = Column(
        Float,
        default=5.0,
        nullable=False,
        comment="Maximum price movement per redistribution cycle"
    )
    max_transaction_percent = Column(
        Float,
        default=10.0,
        nullable=False,
        comment="Maximum single transaction as % of market cap"
    )
    redistribution_pool_percent = Column(
        Float,
        default=25.0,
        nullable=False,
        comment="Percentage of total market cash to redistribute"
    )
    biome_trading_paused = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Emergency pause for all biome trading"
    )
    biome_prices_frozen = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Freeze biome prices (no redistribution)"
    )

    # Feature Toggles
    enable_land_trading = Column(
        Boolean,
        default=True,
        nullable=False
    )
    enable_chat = Column(
        Boolean,
        default=True,
        nullable=False
    )
    enable_registration = Column(
        Boolean,
        default=True,
        nullable=False
    )
    maintenance_mode = Column(
        Boolean,
        default=False,
        nullable=False
    )

    # System Limits
    max_lands_per_user = Column(
        Integer,
        nullable=True
    )
    max_listings_per_user = Column(
        Integer,
        default=10,
        nullable=False
    )
    auction_bid_increment = Column(
        Integer,
        default=100,
        nullable=False
    )
    auction_extend_minutes = Column(
        Integer,
        default=5,
        nullable=False
    )
    max_land_price_bdt = Column(
        Integer,
        nullable=True
    )
    min_land_price_bdt = Column(
        Integer,
        nullable=True
    )

    # Land Allocation Settings (for new users)
    starter_land_enabled = Column(
        Boolean,
        default=True,
        nullable=False
    )
    starter_land_min_size = Column(
        Integer,
        default=36,
        nullable=False
    )
    starter_land_max_size = Column(
        Integer,
        default=1000,
        nullable=False
    )
    starter_land_buffer_units = Column(
        Integer,
        default=1,
        nullable=False
    )
    starter_shape_variation_enabled = Column(
        Boolean,
        default=True,
        nullable=False
    )

    # Meta
    updated_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False
    )

    # Relationship
    updated_by = relationship(
        "User",
        foreign_keys=[updated_by_id]
    )

    def get_biome_multiplier(self, biome: str) -> float:
        """
        Get price multiplier for a biome.

        Args:
            biome: Biome name (forest/desert/grassland/water/snow)

        Returns:
            float: Price multiplier

        Example:
            ```python
            multiplier = config.get_biome_multiplier("forest")
            price = base_price * multiplier
            ```
        """
        multipliers = {
            "forest": self.forest_multiplier,
            "desert": self.desert_multiplier,
            "grassland": self.grassland_multiplier,
            "water": self.water_multiplier,
            "snow": self.snow_multiplier
        }
        return multipliers.get(biome, 1.0)

    def calculate_land_price(self, biome: str) -> int:
        """
        Calculate land price based on biome.

        Args:
            biome: Biome name

        Returns:
            int: Calculated price in BDT
        """
        multiplier = self.get_biome_multiplier(biome)
        return int(self.base_land_price_bdt * multiplier)

    def __repr__(self) -> str:
        """String representation of AdminConfig."""
        return f"<AdminConfig {self.config_id} - Seed {self.world_seed}>"

    def to_dict(self) -> dict:
        """
        Convert config to dictionary for API responses.

        Returns:
            dict: Config data dictionary
        """
        return {
            "config_id": str(self.config_id),
            "world_seed": self.world_seed,
            "noise_frequency": self.noise_frequency,
            "noise_octaves": self.noise_octaves,
            "noise_persistence": self.noise_persistence,
            "noise_lacunarity": self.noise_lacunarity,
            "biome_distribution": {
                "forest": self.biome_forest_percent,
                "grassland": self.biome_grassland_percent,
                "water": self.biome_water_percent,
                "desert": self.biome_desert_percent,
                "snow": self.biome_snow_percent
            },
            "base_land_price_bdt": self.base_land_price_bdt,
            "biome_multipliers": {
                "forest": self.forest_multiplier,
                "grassland": self.grassland_multiplier,
                "water": self.water_multiplier,
                "desert": self.desert_multiplier,
                "snow": self.snow_multiplier
            },
            "transaction_fee_percent": self.transaction_fee_percent,
            "biome_trade_fee_percent": self.biome_trade_fee_percent,
            "biome_market_controls": {
                "max_price_move_percent": self.max_price_move_percent,
                "max_transaction_percent": self.max_transaction_percent,
                "redistribution_pool_percent": self.redistribution_pool_percent,
                "biome_trading_paused": self.biome_trading_paused,
                "biome_prices_frozen": self.biome_prices_frozen
            },
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
