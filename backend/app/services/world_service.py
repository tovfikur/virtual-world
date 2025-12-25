"""
World Generation Service
Deterministic chunk generation using OpenSimplex noise
"""

import hashlib
from typing import Dict, List, Tuple
from opensimplex import OpenSimplex
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.land import Biome
from app.models.admin_config import AdminConfig
from app.services.cache_service import cache_service
from app.config import settings, CACHE_TTLS

logger = logging.getLogger(__name__)


class WorldGenerationService:
    """
    Generates deterministic infinite world chunks using OpenSimplex noise.

    Features:
    - Deterministic generation (same seed = same world)
    - Multiple octaves for varied terrain
    - Biome assignment based on elevation and moisture
    - Chunk-based generation for efficient streaming
    """

    def __init__(self, seed: int = None):
        """
        Initialize world generator with seed.

        Args:
            seed: Random seed for deterministic generation.
                  Uses WORLD_SEED from config if not provided.
        """
        self.seed = seed or settings.WORLD_SEED

        # Initialize noise generators with different seeds for different purposes
        self.elevation_noise = OpenSimplex(seed=self.seed)
        self.moisture_noise = OpenSimplex(seed=self.seed + 1)
        self.temperature_noise = OpenSimplex(seed=self.seed + 2)
        self.detail_noise = OpenSimplex(seed=self.seed + 3)

        # Noise parameters
        self.scale = 0.01  # Base scale for noise (smaller = smoother)
        self.octaves = 4   # Number of noise layers
        self.persistence = 0.5  # How much each octave contributes
        self.lacunarity = 2.0  # Frequency multiplier per octave

        logger.info(f"World generator initialized with seed: {self.seed}")

    def _octave_noise(self, noise_gen: OpenSimplex, x: float, y: float) -> float:
        """
        Generate multi-octave noise for more natural terrain.

        Args:
            noise_gen: OpenSimplex noise generator
            x, y: Coordinates

        Returns:
            Noise value between -1 and 1
        """
        total = 0.0
        frequency = 1.0
        amplitude = 1.0
        max_value = 0.0

        for _ in range(self.octaves):
            total += noise_gen.noise2(
                x * self.scale * frequency,
                y * self.scale * frequency
            ) * amplitude

            max_value += amplitude
            amplitude *= self.persistence
            frequency *= self.lacunarity

        return total / max_value

    def get_elevation(self, x: int, y: int) -> float:
        """
        Get elevation at coordinates.

        Args:
            x, y: World coordinates

        Returns:
            Elevation value between 0 and 1
        """
        noise_value = self._octave_noise(self.elevation_noise, float(x), float(y))
        # Normalize from [-1, 1] to [0, 1]
        return (noise_value + 1.0) / 2.0

    def get_moisture(self, x: int, y: int) -> float:
        """
        Get moisture level at coordinates.

        Args:
            x, y: World coordinates

        Returns:
            Moisture value between 0 and 1
        """
        noise_value = self._octave_noise(self.moisture_noise, float(x), float(y))
        return (noise_value + 1.0) / 2.0

    def get_temperature(self, x: int, y: int) -> float:
        """
        Get temperature at coordinates.

        Args:
            x, y: World coordinates

        Returns:
            Temperature value between 0 and 1
        """
        noise_value = self._octave_noise(self.temperature_noise, float(x), float(y))
        return (noise_value + 1.0) / 2.0

    def get_biome(self, x: int, y: int) -> Biome:
        """
        Determine biome based on elevation, moisture, and temperature.

        Biome Rules:
        - OCEAN: Very low elevation
        - BEACH: Low elevation near water
        - DESERT: High temperature, low moisture
        - PLAINS: Medium everything
        - FOREST: Medium elevation, high moisture
        - MOUNTAIN: High elevation
        - SNOW: Very high elevation or very low temperature

        Args:
            x, y: World coordinates

        Returns:
            Biome enum value
        """
        elevation = self.get_elevation(x, y)
        moisture = self.get_moisture(x, y)
        temperature = self.get_temperature(x, y)

        # Ocean (deep water)
        if elevation < 0.3:
            return Biome.OCEAN

        # Beach (shallow water/shore)
        if elevation < 0.35:
            return Biome.BEACH

        # Snow (high elevation or low temperature)
        if elevation > 0.8 or temperature < 0.2:
            return Biome.SNOW

        # Mountain (high elevation)
        if elevation > 0.65:
            return Biome.MOUNTAIN

        # Desert (hot and dry)
        if temperature > 0.7 and moisture < 0.3:
            return Biome.DESERT

        # Forest (medium elevation, high moisture)
        if moisture > 0.6:
            return Biome.FOREST

        # Plains (default/medium)
        return Biome.PLAINS

    async def calculate_base_price(self, biome: Biome, elevation: float, db: AsyncSession) -> int:
        """
        Calculate base land price in BDT based on biome and elevation.

        Pricing Strategy:
        - PLAINS: Most desirable (flat, buildable) - 100-150 BDT
        - FOREST: Resource-rich - 80-120 BDT
        - BEACH: Scenic - 70-110 BDT
        - MOUNTAIN: Challenging but scenic - 60-100 BDT
        - DESERT: Harsh - 40-70 BDT
        - SNOW: Very harsh - 30-60 BDT
        - OCEAN: Not buildable - 20-40 BDT

        Args:
            biome: Land biome
            elevation: Elevation value (0-1)
            db: Database session for fetching AdminConfig

        Returns:
            Base price in BDT
        """
        # Fetch admin config for biome pricing
        from sqlalchemy import select
        config = await db.scalar(select(AdminConfig))
        
        if not config:
            # Fallback to defaults if config not found
            base_prices = {
                Biome.PLAINS: 125,
                Biome.FOREST: 100,
                Biome.BEACH: 90,
                Biome.MOUNTAIN: 80,
                Biome.DESERT: 55,
                Biome.SNOW: 45,
                Biome.OCEAN: 30
            }
            base = base_prices[biome]
        else:
            # Use configured prices
            base_prices = {
                Biome.PLAINS: config.plains_base_price,
                Biome.FOREST: config.forest_base_price,
                Biome.BEACH: config.beach_base_price,
                Biome.MOUNTAIN: config.mountain_base_price,
                Biome.DESERT: config.desert_base_price,
                Biome.SNOW: config.snow_base_price,
                Biome.OCEAN: config.ocean_base_price
            }
            base = base_prices[biome]

        # Slight variation based on elevation (±20%)
        elevation_factor = 0.8 + (elevation * 0.4)

        return int(base * elevation_factor)

    def calculate_base_price_fallback(self, biome: Biome, elevation: float) -> int:
        """
        Fallback method for calculating base price without database access.
        Used when db session is not available.

        Args:
            biome: Land biome
            elevation: Elevation value (0-1)

        Returns:
            Base price in BDT
        """
        base_prices = {
            Biome.PLAINS: 125,
            Biome.FOREST: 100,
            Biome.BEACH: 90,
            Biome.MOUNTAIN: 80,
            Biome.DESERT: 55,
            Biome.SNOW: 45,
            Biome.OCEAN: 30
        }
        base = base_prices[biome]
        elevation_factor = 0.8 + (elevation * 0.4)
        return int(base * elevation_factor)

    async def generate_chunk(self, chunk_x: int, chunk_y: int, chunk_size: int = 32, db: AsyncSession = None) -> Dict:
        """
        Generate a chunk of land data.

        Args:
            chunk_x: Chunk X coordinate
            chunk_y: Chunk Y coordinate
            chunk_size: Size of chunk (default 32x32)
            db: Database session for fetching pricing config

        Returns:
            Dictionary containing chunk data:
            {
                "chunk_id": "x_y",
                "chunk_x": x,
                "chunk_y": y,
                "chunk_size": size,
                "lands": [...]
            }
        """
        chunk_id = f"{chunk_x}_{chunk_y}"

        # Check cache first
        cache_key = f"chunk:{chunk_id}:{chunk_size}"
        cached_chunk = await cache_service.get(cache_key)

        if cached_chunk:
            logger.debug(f"Cache hit for chunk {chunk_id}")
            return cached_chunk

        lands = []

        # Calculate world coordinates for this chunk
        start_x = chunk_x * chunk_size
        start_y = chunk_y * chunk_size

        for local_y in range(chunk_size):
            for local_x in range(chunk_size):
                # World coordinates
                world_x = start_x + local_x
                world_y = start_y + local_y

                # Generate terrain data
                elevation = self.get_elevation(world_x, world_y)
                moisture = self.get_moisture(world_x, world_y)
                temperature = self.get_temperature(world_x, world_y)
                biome = self.get_biome(world_x, world_y)
                base_price = await self.calculate_base_price(biome, elevation, db) if db else self.calculate_base_price_fallback(biome, elevation)

                land_data = {
                    "x": world_x,
                    "y": world_y,
                    "elevation": round(elevation, 3),
                    "moisture": round(moisture, 3),
                    "temperature": round(temperature, 3),
                    "biome": biome.value,
                    "base_price_bdt": base_price
                }

                lands.append(land_data)

        chunk_data = {
            "chunk_id": chunk_id,
            "chunk_x": chunk_x,
            "chunk_y": chunk_y,
            "chunk_size": chunk_size,
            "seed": self.seed,
            "lands": lands,
            "total_lands": len(lands)
        }

        # Cache the chunk (chunks are immutable)
        await cache_service.set(cache_key, chunk_data, ttl=CACHE_TTLS["chunk"])

        logger.info(f"Generated chunk {chunk_id} with {len(lands)} lands")

        return chunk_data

    async def generate_chunks_batch(
        self,
        chunks: List[Tuple[int, int]],
        chunk_size: int = 32,
        db: AsyncSession = None
    ) -> List[Dict]:
        """
        Generate multiple chunks in batch.

        Args:
            chunks: List of (chunk_x, chunk_y) tuples
            chunk_size: Size of each chunk
            db: Database session for fetching pricing config

        Returns:
            List of chunk data dictionaries
        """
        result = []

        for chunk_x, chunk_y in chunks:
            chunk_data = await self.generate_chunk(chunk_x, chunk_y, chunk_size, db)
            result.append(chunk_data)

        logger.info(f"Generated {len(result)} chunks in batch")

        return result

    def get_land_at(self, x: int, y: int) -> Dict:
        """
        Get land data at specific world coordinates.

        Args:
            x, y: World coordinates

        Returns:
            Land data dictionary
        """
        elevation = self.get_elevation(x, y)
        moisture = self.get_moisture(x, y)
        temperature = self.get_temperature(x, y)
        biome = self.get_biome(x, y)
        base_price = self.calculate_base_price_fallback(biome, elevation)

        return {
            "x": x,
            "y": y,
            "elevation": round(elevation, 3),
            "moisture": round(moisture, 3),
            "temperature": round(temperature, 3),
            "biome": biome.value,
            "base_price_bdt": base_price
        }


# Global instance
world_service = WorldGenerationService()
