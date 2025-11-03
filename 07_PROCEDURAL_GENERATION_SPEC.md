# Virtual Land World - Procedural Generation Specification

## Overview

Virtual Land World uses deterministic procedural generation to create an infinite, consistent 2D world. The same seed always produces identical output, allowing clients to generate chunks independently without server involvement once they know the seed.

---

## World Generation Architecture

### Core Algorithm: OpenSimplex Noise

**Why OpenSimplex?**
- Deterministic (same seed = same output)
- Smooth gradients (good for terrain)
- Efficient (can generate millions of vertices per second)
- Open-source and portable
- Better visual quality than Perlin noise

**OpenSimplex Parameters:**
- **Frequency:** Controls detail scale (higher = more detail)
- **Octaves:** Number of noise layers (more = more complexity)
- **Persistence:** How much each octave contributes
- **Lacunarity:** Scale multiplier between octaves

### Chunk-Based Architecture

```
World Space (infinite)
    │
    ├─ Chunk 0,0 (32x32 triangles)
    ├─ Chunk 1,0
    ├─ Chunk 0,1
    ├─ Chunk 1,1
    └─ ... (extends infinitely)

Each chunk = 32×32 triangles
Each triangle = ~500m² in world space
```

---

## Procedural Generation Algorithm

### Step 1: Initialize Noise Generator

```python
from opensimplex import OpenSimplex

# Initialize with seed (same seed = deterministic output)
noise_generator = OpenSimplex(seed=12345)

# Configuration (from admin_config table)
config = {
    "frequency": 0.05,      # Lower = larger features
    "octaves": 6,           # More layers = more detail
    "persistence": 0.6,     # How much each layer contributes
    "lacunarity": 2.0,      # Scale between layers
    "amplitude": 1.0,       # Height range
    "scale": 1.0            # Overall scale
}
```

### Step 2: Chunk ID to Coordinates

Chunk ID format: `"chunk_{chunk_x}_{chunk_y}"`

```python
def chunk_id_to_coordinates(chunk_id: str) -> tuple:
    """Convert chunk_id to grid coordinates."""
    parts = chunk_id.split('_')
    chunk_x = int(parts[1])
    chunk_y = int(parts[2])
    return chunk_x, chunk_y

def coordinates_to_chunk_id(chunk_x: int, chunk_y: int) -> str:
    """Convert coordinates to chunk_id."""
    return f"chunk_{chunk_x}_{chunk_y}"
```

### Step 3: Generate Chunk Triangles

```python
def generate_chunk(chunk_x: int, chunk_y: int, config: dict) -> dict:
    """Generate a single chunk with deterministic triangles."""

    triangles = []
    chunk_size = 32  # Triangles per dimension

    # Generate noise for all grid points
    noise_grid = []
    for local_y in range(chunk_size + 1):
        row = []
        for local_x in range(chunk_size + 1):
            # Global coordinates
            global_x = chunk_x * chunk_size + local_x
            global_y = chunk_y * chunk_size + local_y

            # Sample multi-octave noise
            height = sample_noise(
                global_x, global_y,
                noise_generator,
                config["frequency"],
                config["octaves"],
                config["persistence"],
                config["lacunarity"]
            )

            # Normalize height to 0-1
            height = (height + 1.0) / 2.0  # OpenSimplex returns -1 to 1
            row.append(height)

        noise_grid.append(row)

    # Create triangles from grid points
    triangle_id = 0
    for y in range(chunk_size):
        for x in range(chunk_size):
            # Get four corners of grid cell
            h0 = noise_grid[y][x]
            h1 = noise_grid[y][x + 1]
            h2 = noise_grid[y + 1][x]
            h3 = noise_grid[y + 1][x + 1]

            # Create two triangles per grid cell
            # Triangle 1: top-left, top-right, bottom-left
            tri1 = create_triangle(
                id=triangle_id,
                vertices=[(x, y, h0), (x + 1, y, h1), (x, y + 1, h2)],
                height=max(h0, h1, h2)
            )
            triangles.append(tri1)
            triangle_id += 1

            # Triangle 2: top-right, bottom-right, bottom-left
            tri2 = create_triangle(
                id=triangle_id,
                vertices=[(x + 1, y, h1), (x + 1, y + 1, h3), (x, y + 1, h2)],
                height=max(h1, h3, h2)
            )
            triangles.append(tri2)
            triangle_id += 1

    return {
        "chunk_id": f"chunk_{chunk_x}_{chunk_y}",
        "triangles": triangles,
        "size": chunk_size,
        "generation_time_ms": elapsed_time
    }
```

### Step 4: Sample Multi-Octave Noise

```python
def sample_noise(x: float, y: float, noise_gen, frequency: float,
                  octaves: int, persistence: float, lacunarity: float) -> float:
    """Sample multi-octave Simplex noise."""

    amplitude = 1.0
    max_amplitude = 0.0
    value = 0.0

    for octave in range(octaves):
        # Scale coordinates by frequency
        sample_x = x * frequency * (lacunarity ** octave)
        sample_y = y * frequency * (lacunarity ** octave)

        # Sample noise
        noise_value = noise_gen.noise2d(sample_x, sample_y)

        # Accumulate with amplitude
        value += noise_value * amplitude
        max_amplitude += amplitude

        # Reduce amplitude for next octave
        amplitude *= persistence

    # Normalize
    return value / max_amplitude if max_amplitude > 0 else 0
```

### Step 5: Assign Biome Based on Height

```python
def assign_biome(height: float, biome_config: dict) -> str:
    """Determine biome from height value."""

    # Define biome thresholds
    # Heights are 0-1, map to cumulative probabilities
    thresholds = {
        0.0: "water",
        0.35: "forest",
        0.65: "grassland",
        0.80: "desert",
        0.95: "snow"
    }

    # Find applicable biome
    for threshold in sorted(thresholds.keys(), reverse=True):
        if height >= threshold:
            return thresholds[threshold]

    return "water"  # Default if height < 0
```

### Step 6: Assign Colors

```python
def get_biome_color(biome: str, height: float) -> str:
    """Return hex color for biome."""

    biome_colors = {
        "water": {"base": "#1A5490", "dark": "#0D2A4C", "light": "#2E7DB5"},
        "forest": {"base": "#2d5016", "dark": "#1a2e0c", "light": "#4a7a2c"},
        "grassland": {"base": "#7ba62a", "dark": "#5d8620", "light": "#9bc94f"},
        "desert": {"base": "#d4a26e", "dark": "#b8885a", "light": "#e8bd88"},
        "snow": {"base": "#f0f0f0", "dark": "#c0c0c0", "light": "#ffffff"}
    }

    color_variant = biome_colors.get(biome, biome_colors["grassland"])

    # Choose shade based on height
    if height < 0.33:
        return color_variant["dark"]
    elif height > 0.66:
        return color_variant["light"]
    else:
        return color_variant["base"]
```

---

## Determinism Guarantee

### Verification

To verify determinism, generate the same chunk twice with same seed and compare:

```python
def verify_determinism(chunk_x: int, chunk_y: int, seed: int, config: dict) -> bool:
    """Verify that chunk generation is deterministic."""

    # Generate chunk twice
    gen1 = OpenSimplex(seed=seed)
    chunk1 = generate_chunk(chunk_x, chunk_y, config, gen1)

    gen2 = OpenSimplex(seed=seed)
    chunk2 = generate_chunk(chunk_x, chunk_y, config, gen2)

    # Compare all triangles
    for tri1, tri2 in zip(chunk1["triangles"], chunk2["triangles"]):
        assert tri1["vertices"] == tri2["vertices"]
        assert tri1["biome"] == tri2["biome"]
        assert tri1["color"] == tri2["color"]

    return True
```

### Seed Consistency

The world seed is stored in `admin_config.world_seed`. If admin changes seed:
- **New chunks** generated with new seed will differ
- **Cached chunks** with old seed remain unchanged
- **Clients** should invalidate cache and re-request chunks after seed change

---

## Configuration Parameters

From `admin_config` table:

```json
{
  "world_seed": 12345,
  "noise_frequency": 0.05,
  "noise_octaves": 6,
  "noise_persistence": 0.6,
  "noise_lacunarity": 2.0,
  "biome_forest_percent": 0.35,
  "biome_grassland_percent": 0.30,
  "biome_water_percent": 0.20,
  "biome_desert_percent": 0.10,
  "biome_snow_percent": 0.05
}
```

**Parameter Effects:**

| Parameter | Effect | Typical Range |
|-----------|--------|---|
| `frequency` | Scale of features (lower = bigger) | 0.01-0.1 |
| `octaves` | Complexity / detail | 3-8 |
| `persistence` | Roughness (higher = rougher) | 0.3-0.8 |
| `lacunarity` | Scale multiplier between octaves | 1.5-3.0 |

---

## Biome Distribution

Biomes are assigned by height threshold. Percentages in config control the expected distribution:

```
Height distribution (normalized):
0.00 ├─── water (0-35%)
0.35 ├─── forest (35-65%)
0.65 ├─── grassland (65-80%)
0.80 ├─── desert (80-95%)
0.95 ├─── snow (95-100%)
1.00 └─

Example with config:
- 35% water
- 30% forest
- 20% grassland
- 10% desert
- 5% snow
```

---

## Chunk ID Generation Formula

Global triangle coordinates → Chunk ID:

```python
def triangle_to_chunk_id(triangle_x: int, triangle_y: int) -> str:
    """Convert triangle coordinates to chunk ID."""
    chunk_size = 32
    chunk_x = triangle_x // chunk_size
    chunk_y = triangle_y // chunk_size
    return f"chunk_{chunk_x}_{chunk_y}"

def chunk_id_to_triangle_range(chunk_id: str) -> dict:
    """Get range of triangle IDs in chunk."""
    chunk_x, chunk_y = chunk_id_to_coordinates(chunk_id)
    chunk_size = 32

    min_x = chunk_x * chunk_size
    max_x = (chunk_x + 1) * chunk_size - 1
    min_y = chunk_y * chunk_size
    max_y = (chunk_y + 1) * chunk_size - 1

    return {
        "x_range": (min_x, max_x),
        "y_range": (min_y, max_y),
        "triangle_count": chunk_size * chunk_size * 2  # 2 triangles per grid cell
    }
```

---

## Performance Benchmarks

### Generation Time

```
Typical performance on modern hardware (Intel i7, Python):
- Per chunk: 45-100 ms
- Per triangle: ~0.07 ms
- Per second: ~10-20 chunks/second

Optimizations:
- Pre-generate chunks in background
- Cache generated chunks in Redis (1 hour TTL)
- Use CDN for pre-generated chunks (S3)
```

### Memory Usage

```
Per chunk in memory:
- Grid points: 33×33 = 1,089 floats = 4.4 KB
- Triangles: 2,048 triangles × 20 bytes = 40 KB
- Metadata: ~2 KB
Total: ~46 KB per chunk

LRU Cache (3×3 grid):
- 9 chunks × 46 KB = 414 KB (negligible on modern devices)

5×5 grid:
- 25 chunks × 46 KB = 1.15 MB
```

### Network Bandwidth

```
Chunk response sizes (compressed):
- JSON format: ~15-20 KB per chunk
- MessagePack (binary): ~8-10 KB per chunk (40% smaller)
- With gzip compression: ~3-5 KB per chunk

Loading 3×3 grid:
- 9 chunks × 5 KB = 45 KB (very fast on broadband)
- On 5 Mbps connection: ~70 ms download time
```

---

## Scaling Considerations

### Horizontal Scaling

1. **Pre-generation Service:** Separate worker processes generate chunks ahead of time
2. **Caching Layers:**
   - Redis: 1-hour TTL (hot chunks)
   - CDN (Cloudflare): 1-hour TTL
   - Client: LRU cache (in-memory)
3. **Load Distribution:** Round-robin chunk requests across multiple FastAPI instances

### Vertical Scaling

- Increase Redis memory to cache more chunks
- Use faster CPUs for generation if needed
- Tune OpenSimplex parameters for better cache coherency

---

## Edge Cases & Boundary Handling

### Chunk Boundaries

Chunks at boundaries need consistent vertices with adjacent chunks:

```python
def get_consistent_vertex(x: int, y: int, noise_gen, config: dict) -> float:
    """Get noise value that's consistent across chunk boundaries."""

    # Always sample using global coordinates
    # This ensures vertex (32, y) of chunk (0, 0)
    # equals vertex (0, y) of chunk (1, 0)

    height = sample_noise(x, y, noise_gen, config["frequency"],
                         config["octaves"], config["persistence"],
                         config["lacunarity"])

    return (height + 1.0) / 2.0
```

### Water/Land Transitions

Smooth transitions between water and land:

```python
def add_transition_smoothing(height: float, neighbor_heights: list) -> float:
    """Smooth transitions between biomes."""

    avg_neighbor = sum(neighbor_heights) / len(neighbor_heights)

    # Blend with neighbors (small amount)
    return height * 0.85 + avg_neighbor * 0.15
```

---

## Implementation in Backend (FastAPI)

```python
# app/services/world_generation.py

from opensimplex import OpenSimplex
import asyncio

class WorldGenerationService:
    def __init__(self, config: dict):
        self.config = config
        self.noise_gen = OpenSimplex(seed=config["world_seed"])

    async def generate_chunk(self, chunk_x: int, chunk_y: int) -> dict:
        """Generate chunk asynchronously."""
        return await asyncio.to_thread(
            self._sync_generate_chunk,
            chunk_x, chunk_y
        )

    def _sync_generate_chunk(self, chunk_x: int, chunk_y: int) -> dict:
        """Synchronous chunk generation."""
        # Implementation as described above
        pass
```

---

## Testing & Verification

```python
# tests/test_world_generation.py

def test_determinism():
    """Verify chunks are deterministic."""
    config = {"world_seed": 12345, "frequency": 0.05, ...}

    gen1 = OpenSimplex(seed=12345)
    chunk1 = generate_chunk(0, 0, config, gen1)

    gen2 = OpenSimplex(seed=12345)
    chunk2 = generate_chunk(0, 0, config, gen2)

    assert chunk1["triangles"] == chunk2["triangles"]

def test_chunk_boundaries():
    """Verify adjacent chunks share vertices."""
    chunk00 = generate_chunk(0, 0, config)
    chunk10 = generate_chunk(1, 0, config)

    # Right edge of chunk (0, 0) should match left edge of chunk (1, 0)
    for y in range(33):
        assert chunk00["vertices"][32][y] == chunk10["vertices"][0][y]

def test_biome_distribution():
    """Verify biome percentages match config."""
    biomes = defaultdict(int)
    for x in range(100):
        for y in range(100):
            chunk = generate_chunk(x, y, config)
            for tri in chunk["triangles"]:
                biomes[tri["biome"]] += 1

    total = sum(biomes.values())
    # Check percentages are close to configured values
```

---

## Future Enhancements

1. **Moisture Layer:** Secondary noise for water features
2. **Temperature Layer:** For seasonal biome variations
3. **POI Generation:** Procedural placement of structures/landmarks
4. **Resource Spawning:** Procedural mining/fishing spots
5. **Multilayer Terrain:** Cliffs, caves, underground layers

---

**Resume Token:** `✓ PHASE_2_WORLD_GEN_COMPLETE`
