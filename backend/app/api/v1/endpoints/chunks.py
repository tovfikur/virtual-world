"""
Chunk endpoints
World generation and chunk retrieval
"""

from fastapi import APIRouter, HTTPException, status, Query, Body, Path
from typing import List, Tuple
import logging

from app.services.world_service import world_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chunks", tags=["chunks"])


@router.get("/{chunk_x}/{chunk_y}")
async def get_chunk(
    chunk_x: int,
    chunk_y: int,
    chunk_size: int = Query(32, ge=8, le=64, description="Chunk size (8-64)")
):
    """
    Get a generated chunk at specified coordinates.

    Returns a chunk containing terrain data for all lands in the chunk.
    Chunks are generated deterministically and cached.

    Args:
        chunk_x: Chunk X coordinate
        chunk_y: Chunk Y coordinate
        chunk_size: Size of chunk (default 32x32, max 64x64)

    Returns:
        Chunk data with land information
    """
    try:
        chunk_data = world_service.generate_chunk(chunk_x, chunk_y, chunk_size)
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
    chunk_size: int = Query(32, ge=8, le=64)
):
    """
    Get multiple chunks in a single request.

    Useful for loading a region of chunks at once (e.g., viewport streaming).

    Args:
        chunks: List of [chunk_x, chunk_y] coordinate pairs (max 25 chunks)
        chunk_size: Size of each chunk

    Returns:
        List of chunk data
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
        chunks_data = world_service.generate_chunks_batch(chunk_tuples, chunk_size)

        return {
            "chunks": chunks_data,
            "total": len(chunks_data),
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
