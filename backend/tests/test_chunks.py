"""
World Generation / Chunks Tests
Test procedural world generation
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_chunk():
    """Test getting a chunk"""
    response = client.get("/api/v1/chunks/0/0")
    assert response.status_code == 200
    data = response.json()
    assert "chunk_x" in data
    assert "chunk_y" in data
    assert "lands" in data
    assert len(data["lands"]) > 0


def test_chunk_determinism():
    """Test that same chunk returns same data"""
    response1 = client.get("/api/v1/chunks/5/5")
    response2 = client.get("/api/v1/chunks/5/5")

    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    # Check first land matches
    assert data1["lands"][0]["biome"] == data2["lands"][0]["biome"]
    assert data1["lands"][0]["elevation"] == data2["lands"][0]["elevation"]


def test_get_chunk_batch():
    """Test batch chunk retrieval"""
    response = client.post(
        "/api/v1/chunks/batch",
        json={
            "chunk_coords": [[0, 0], [0, 1], [1, 0]],
            "chunk_size": 32
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "chunks" in data
    assert len(data["chunks"]) == 3


def test_get_world_info():
    """Test getting world information"""
    response = client.get("/api/v1/chunks/info")
    assert response.status_code == 200
    data = response.json()
    assert "seed" in data
    assert "default_chunk_size" in data
    assert "biome_types" in data


def test_biome_variety():
    """Test that multiple biomes exist"""
    biomes = set()

    for x in range(10):
        for y in range(10):
            response = client.get(f"/api/v1/chunks/{x}/{y}")
            if response.status_code == 200:
                data = response.json()
                for land in data["lands"][:10]:  # Check first 10 lands
                    biomes.add(land["biome"])

    # Should have at least 3 different biomes
    assert len(biomes) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
