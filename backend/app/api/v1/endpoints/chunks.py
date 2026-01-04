"""
Chunk endpoints
World generation and chunk retrieval
"""

from fastapi import APIRouter, HTTPException, status, Query, Body, Path, Depends
from typing import List, Tuple, Dict, Optional, Set
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import uuid

from app.services.world_service import world_service
from app.db.session import get_db
from app.models.land import Land, Biome
from app.models.land_chat_access import LandChatAccess
from app.models.listing_land import ListingLand
from app.models.listing import Listing, ListingStatus
from app.models.admin_config import AdminConfig
from app.dependencies import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chunks", tags=["chunks"])


async def _calculate_unclaimed_land_price(
    land_data: Dict,
    db: AsyncSession
) -> int:
    """
    Recalculate unclaimed land price based on current admin configuration.
    
    For unowned/unclaimed lands coming from chunk generation,
    ensure prices reflect the latest admin economic settings.
    
    Args:
        land_data: Land data dict with biome and elevation
        db: Database session
        
    Returns:
        Recalculated price in BDT
    """
    # Fetch current admin config
    result = await db.execute(select(AdminConfig).limit(1))
    config = result.scalar_one_or_none()
    
    if not config:
        # Fallback to stored price if no config
        return int(land_data.get("price_base_bdt", 100))
    
    # Map biome string to enum
    biome_str = land_data.get("biome", "plains")
    try:
        biome = Biome(biome_str)
    except ValueError:
        biome = Biome.PLAINS
    
    # Get biome-specific base price
    biome_base_prices = {
        Biome.PLAINS: config.plains_base_price,
        Biome.FOREST: config.forest_base_price,
        Biome.BEACH: config.beach_base_price,
        Biome.MOUNTAIN: config.mountain_base_price,
        Biome.DESERT: config.desert_base_price,
        Biome.SNOW: config.snow_base_price,
        Biome.OCEAN: config.ocean_base_price
    }
    
    base = biome_base_prices.get(biome, 100)
    
    # Apply elevation factor
    elevation = land_data.get("elevation", 0.5)
    if elevation is None:
        elevation = 0.5
    # Clamp elevation to [0, 1]
    elevation = max(0.0, min(1.0, elevation))
    
    min_factor = float(config.elevation_price_min_factor) if config.elevation_price_min_factor else 0.8
    max_factor = float(config.elevation_price_max_factor) if config.elevation_price_max_factor else 1.2
    
    # Ensure min_factor <= max_factor
    if min_factor > max_factor:
        min_factor, max_factor = max_factor, min_factor
    
    elevation_factor = min_factor + (elevation * (max_factor - min_factor))
    
    calculated_price = int(base * elevation_factor)
    return calculated_price


async def enrich_chunk_with_ownership(
    chunk_data: Dict,
    db: AsyncSession,
    user_uuid: Optional[uuid.UUID] = None,
) -> Dict:
    """
    Enrich chunk data with ownership, fencing, and current pricing information.

    Args:
        chunk_data: Generated chunk data from world service
        db: Database session

    Returns:
        Enriched chunk data with fencing flags and recalculated prices
    """
    # Calculate coordinate range for this chunk
    lands = chunk_data["lands"]
    if not lands:
        return chunk_data

    # Get min/max coordinates for efficient query
    x_coords = [land["x"] for land in lands]
    y_coords = [land["y"] for land in lands]
    min_x, max_x = min(x_coords), max(x_coords)
    min_y, max_y = min(y_coords), max(y_coords)

    # Query for owned lands in this chunk area
    result = await db.execute(
        select(Land.x, Land.y, Land.land_id, Land.owner_id, Land.fenced)
        .where(
            and_(
                Land.x >= min_x,
                Land.x <= max_x,
                Land.y >= min_y,
                Land.y <= max_y,
                Land.owner_id.isnot(None)
            )
        )
    )

    owned_lands = result.all()
    owned_land_ids: List[uuid.UUID] = []

    # Create a lookup map for owned lands with all ownership data
    ownership_lookup = {
        (row.x, row.y): {
            "land_id": str(row.land_id),
            "owner_id": str(row.owner_id),
            "fenced": row.fenced,
        }
        for row in owned_lands
    }
    owned_land_ids = [row.land_id for row in owned_lands]

    guest_access_ids: Set[str] = set()
    if user_uuid and owned_land_ids:
        access_result = await db.execute(
            select(LandChatAccess.land_id)
            .where(
                LandChatAccess.land_id.in_(owned_land_ids),
                LandChatAccess.user_id == user_uuid,
                LandChatAccess.can_read.is_(True),
            )
        )
        guest_access_ids = {str(land_id) for land_id in access_result.scalars().all()}

    # Query for lands with active marketplace listings
    listed_land_ids: Set[str] = set()
    if owned_land_ids:
        listing_result = await db.execute(
            select(ListingLand.land_id)
            .join(Listing)
            .where(
                and_(
                    ListingLand.land_id.in_(owned_land_ids),
                    Listing.status == ListingStatus.ACTIVE
                )
            )
        )
        listed_land_ids = {str(land_id) for land_id in listing_result.scalars().all()}

    user_id_str = str(user_uuid) if user_uuid else None

    # Enrich land data with ownership, fencing, and recalculated pricing
    for land in lands:
        coord_key = (land["x"], land["y"])
        if coord_key in ownership_lookup:
            # Land is owned - add ownership data
            ownership_entry = ownership_lookup[coord_key]
            land["land_id"] = ownership_entry["land_id"]
            land["owner_id"] = ownership_entry["owner_id"]
            land["fenced"] = ownership_entry["fenced"]

            if land["fenced"]:
                has_guest_access = ownership_entry["land_id"] in guest_access_ids
                is_owner = (
                    user_id_str is not None
                    and ownership_entry["owner_id"] == user_id_str
                )
                land["guest_access"] = has_guest_access or is_owner
            else:
                land["guest_access"] = False
            
            # Check if land is listed for sale
            land["for_sale"] = ownership_entry["land_id"] in listed_land_ids
        else:
            # Land is not owned
            land["fenced"] = False
            land["guest_access"] = False
            land["for_sale"] = False
        
        # Recalculate price based on current admin config for both owned and unowned lands
        try:
            current_price = await _calculate_unclaimed_land_price(land, db)
            land["price_base_bdt"] = current_price
        except Exception as e:
            logger.warning(f"Failed to recalculate price for land at ({land['x']}, {land['y']}): {e}")
            # Keep the generated price if calculation fails

    return chunk_data


@router.get("/{chunk_x}/{chunk_y}")
async def get_chunk(
    chunk_x: int,
    chunk_y: int,
    chunk_size: int = Query(32, ge=8, le=64, description="Chunk size (8-64)"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Get a generated chunk at specified coordinates.

    Returns a chunk containing terrain data for all lands in the chunk.
    Chunks are generated deterministically and cached.
    Includes fencing information for owned lands.

    Args:
        chunk_x: Chunk X coordinate
        chunk_y: Chunk Y coordinate
        chunk_size: Size of chunk (default 32x32, max 64x64)

    Returns:
        Chunk data with land information including fencing flags
    """
    try:
        chunk_data = await world_service.generate_chunk(chunk_x, chunk_y, chunk_size, db)
        # Enrich with ownership/fencing data
        user_uuid = None
        if current_user:
            try:
                user_uuid = uuid.UUID(current_user["sub"])
            except (ValueError, KeyError, TypeError):
                user_uuid = None
        chunk_data = await enrich_chunk_with_ownership(chunk_data, db, user_uuid)
        return chunk_data
    except Exception as e:
        logger.error(f"Failed to generate chunk {chunk_x},{chunk_y}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate chunk"
        )


@router.post("/batch")
async def get_chunks_batch(
    chunks: List[Tuple[int, int]] = Body(
        ...,
        description="List of [chunk_x, chunk_y] coordinate pairs",
        example=[[0, 0], [0, 1], [1, 0], [1, 1]]
    ),
    chunk_size: int = Query(32, ge=8, le=64),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Get multiple chunks in a single request.

    Useful for loading a region of chunks at once (e.g., viewport streaming).
    Includes fencing information for owned lands.

    Args:
        chunks: List of [chunk_x, chunk_y] coordinate pairs (max 25 chunks)
        chunk_size: Size of each chunk

    Returns:
        List of chunk data with fencing information
    """
    # Limit batch size to prevent abuse
    if len(chunks) > 25:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 25 chunks per batch request"
        )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one chunk coordinate required"
        )

    try:
        # Convert list of lists to list of tuples
        chunk_tuples = [tuple(c) for c in chunks]
        chunks_data = await world_service.generate_chunks_batch(chunk_tuples, chunk_size, db)
        user_uuid = None
        if current_user:
            try:
                user_uuid = uuid.UUID(current_user["sub"])
            except (ValueError, KeyError, TypeError):
                user_uuid = None

        # Enrich all chunks with ownership/fencing data
        enriched_chunks = []
        for chunk_data in chunks_data:
            enriched_chunk = await enrich_chunk_with_ownership(
                chunk_data,
                db,
                user_uuid,
            )
            enriched_chunks.append(enriched_chunk)

        return {
            "chunks": enriched_chunks,
            "total": len(enriched_chunks),
            "chunk_size": chunk_size
        }
    except Exception as e:
        logger.error(f"Failed to generate chunk batch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate chunks"
        )


@router.get("/land/{x}/{y}")
async def get_land_at_coordinates(
    x: int = Path(..., description="World X coordinate"),
    y: int = Path(..., description="World Y coordinate")
):
    """
    Get land data at specific world coordinates.

    Returns terrain information for a single land parcel.

    Args:
        x: World X coordinate
        y: World Y coordinate

    Returns:
        Land terrain data
    """
    try:
        land_data = world_service.get_land_at(x, y)
        return land_data
    except Exception as e:
        logger.error(f"Failed to get land at {x},{y}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate land data"
        )


@router.get("/preview/{chunk_x}/{chunk_y}")
async def preview_chunk(
    chunk_x: int,
    chunk_y: int,
    chunk_size: int = Query(32, ge=8, le=64)
):
    """
    Get a simplified preview of a chunk (biomes only).

    Returns only biome information for lightweight preview rendering.

    Args:
        chunk_x: Chunk X coordinate
        chunk_y: Chunk Y coordinate
        chunk_size: Size of chunk

    Returns:
        Simplified chunk data with biomes only
    """
    try:
        chunk_data = world_service.generate_chunk(chunk_x, chunk_y, chunk_size)

        # Simplify data for preview
        preview_data = {
            "chunk_id": chunk_data["chunk_id"],
            "chunk_x": chunk_data["chunk_x"],
            "chunk_y": chunk_data["chunk_y"],
            "chunk_size": chunk_data["chunk_size"],
            "biomes": [
                {
                    "x": land["x"],
                    "y": land["y"],
                    "biome": land["biome"]
                }
                for land in chunk_data["lands"]
            ]
        }

        return preview_data
    except Exception as e:
        logger.error(f"Failed to generate chunk preview {chunk_x},{chunk_y}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate chunk preview"
        )


@router.get("/info")
async def get_world_info():
    """
    Get world generation information.

    Returns:
        World seed and generation parameters
    """
    return {
        "seed": world_service.seed,
        "default_chunk_size": 32,
        "available_biomes": [
            "ocean",
            "beach",
            "plains",
            "forest",
            "desert",
            "mountain",
            "snow"
        ],
        "noise_parameters": {
            "octaves": world_service.octaves,
            "scale": world_service.scale,
            "persistence": world_service.persistence,
            "lacunarity": world_service.lacunarity
        },
        "deterministic": True,
        "infinite": True
    }
