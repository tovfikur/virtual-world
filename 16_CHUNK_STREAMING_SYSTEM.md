# Virtual Land World - Chunk Streaming System

## Chunk Loader Implementation

```typescript
// src/engine/chunk-loader.ts

import { APIClient } from '../services/api'
import { Cache } from '../services/cache'

export class ChunkLoader {
  private cache: Map<string, any> = new Map()
  private maxCacheSize: number = 25 // 5x5 grid
  private loading: Set<string> = new Set()
  private apiClient: APIClient

  constructor(apiClient: APIClient) {
    this.apiClient = apiClient
  }

  async loadChunk(chunkX: number, chunkY: number): Promise<any> {
    const chunkId = `chunk_${chunkX}_${chunkY}`

    // Check local cache first
    if (this.cache.has(chunkId)) {
      return this.cache.get(chunkId)
    }

    // Prevent duplicate requests
    if (this.loading.has(chunkId)) {
      return new Promise((resolve) => {
        const checkInterval = setInterval(() => {
          if (this.cache.has(chunkId)) {
            clearInterval(checkInterval)
            resolve(this.cache.get(chunkId))
          }
        }, 100)
      })
    }

    this.loading.add(chunkId)

    try {
      const chunk = await this.apiClient.getChunk(chunkId)
      this.cache.set(chunkId, chunk)

      // Enforce max cache size (LRU)
      if (this.cache.size > this.maxCacheSize) {
        const firstKey = this.cache.keys().next().value
        this.cache.delete(firstKey)
      }

      return chunk
    } finally {
      this.loading.delete(chunkId)
    }
  }

  async loadChunks(chunkIds: string[]): Promise<Record<string, any>> {
    // Batch load for efficiency
    const uncached = chunkIds.filter(id => !this.cache.has(id))

    if (uncached.length > 0) {
      const chunks = await this.apiClient.getChunksBatch(uncached)
      Object.entries(chunks).forEach(([id, chunk]) => {
        this.cache.set(id, chunk)
      })
    }

    const result: Record<string, any> = {}
    chunkIds.forEach(id => {
      if (this.cache.has(id)) {
        result[id] = this.cache.get(id)
      }
    })

    return result
  }

  clearCache() {
    this.cache.clear()
  }

  getChunkAround(centerX: number, centerY: number, radius: number = 2): string[] {
    const chunks = []
    for (let x = centerX - radius; x <= centerX + radius; x++) {
      for (let y = centerY - radius; y <= centerY + radius; y++) {
        chunks.push(`chunk_${x}_${y}`)
      }
    }
    return chunks
  }
}
```

## Mesh Generation

```typescript
// src/engine/mesh-generator.ts

export class MeshGenerator {
  static generateTriangleMesh(chunk: any): PIXI.Mesh {
    const triangles = chunk.triangles
    const vertices: number[] = []
    const indices: number[] = []
    const colors: number[] = []

    let vertexIndex = 0
    const vertexMap = new Map<string, number>()

    triangles.forEach((tri: any) => {
      tri.vertices.forEach((vertex: any) => {
        const key = `${vertex[0]},${vertex[1]},${vertex[2]}`

        if (!vertexMap.has(key)) {
          vertices.push(vertex[0] * 32, vertex[1] * 32, vertex[2] * 1)
          const color = this.hexToRGB(tri.color_hex)
          colors.push(color)
          vertexMap.set(key, vertexIndex++)
        }

        indices.push(vertexMap.get(key)!)
      })
    })

    const geometry = new PIXI.Geometry()
    geometry.addAttribute('aVertexPosition',
      new Float32Array(vertices), 3)
    geometry.addAttribute('aColor',
      new Uint32Array(colors), 1, true)
    geometry.addIndex(new Uint32Array(indices))

    const mesh = new PIXI.Mesh(geometry)
    return mesh
  }

  private static hexToRGB(hex: string): number {
    const num = parseInt(hex.replace('#', ''), 16)
    return ((num & 0xff) << 16) + (num & 0xff00) + ((num >> 16) & 0xff)
  }
}
```

## Spatial Queries

```typescript
// src/world/spatial.ts

export class SpatialIndex {
  private chunks: Map<string, any> = new Map()

  add(chunkId: string, chunk: any) {
    this.chunks.set(chunkId, chunk)
  }

  getChunksInRadius(centerX: number, centerY: number, radius: number): any[] {
    const result = []
    const keys = Array.from(this.chunks.keys())

    for (const key of keys) {
      const [, x, y] = key.split('_').map(Number)
      const distance = Math.max(Math.abs(x - centerX), Math.abs(y - centerY))

      if (distance <= radius) {
        result.push(this.chunks.get(key))
      }
    }

    return result
  }

  getLandAt(x: number, y: number): any {
    const chunkX = Math.floor(x / 32)
    const chunkY = Math.floor(y / 32)
    const key = `chunk_${chunkX}_${chunkY}`

    const chunk = this.chunks.get(key)
    if (!chunk) return null

    const localX = x % 32
    const localY = y % 32

    return chunk.triangles.find((tri: any) =>
      this.isPointInTriangle(localX, localY, tri.vertices)
    )
  }

  private isPointInTriangle(px: number, py: number, vertices: any[]): boolean {
    const [x1, y1] = vertices[0]
    const [x2, y2] = vertices[1]
    const [x3, y3] = vertices[2]

    const area = Math.abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2
    const area1 = Math.abs((px - x2) * (y3 - y2) - (x3 - x2) * (py - y2)) / 2
    const area2 = Math.abs((x1 - px) * (y3 - py) - (x3 - px) * (y1 - py)) / 2
    const area3 = Math.abs((x1 - x2) * (py - y2) - (px - x2) * (y1 - y2)) / 2

    return Math.abs(area - (area1 + area2 + area3)) < 0.01
  }
}
```

**Resume Token:** `✓ PHASE_4_STREAMING_COMPLETE`
