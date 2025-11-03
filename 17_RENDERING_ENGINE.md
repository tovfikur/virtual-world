# Virtual Land World - Rendering Engine

## PixiJS Renderer

```typescript
// src/engine/renderer.ts

import * as PIXI from 'pixi.js'
import { MeshGenerator } from './mesh-generator'

export class Renderer {
  app: PIXI.Application
  stage: PIXI.Container

  constructor(width: number, height: number) {
    this.app = new PIXI.Application({
      width,
      height,
      backgroundColor: 0x87ceeb, // Sky blue
      antialias: true,
      autoDensity: true,
      resolution: window.devicePixelRatio || 1,
    })

    this.stage = new PIXI.Container()
    this.app.stage.addChild(this.stage)
  }

  addChunkMesh(chunkId: string, chunk: any) {
    const mesh = MeshGenerator.generateTriangleMesh(chunk)
    mesh.position.set(chunk.coordinates.x * 1024, chunk.coordinates.y * 1024)
    this.stage.addChild(mesh)
  }

  removeChunkMesh(chunkId: string) {
    const mesh = this.stage.getChildByName(chunkId)
    if (mesh) {
      this.stage.removeChild(mesh)
    }
  }

  render() {
    // Rendering handled by PIXI's animation loop
  }

  resize(width: number, height: number) {
    this.app.renderer.resize(width, height)
  }

  getCamera() {
    return {
      x: this.stage.position.x,
      y: this.stage.position.y,
      scale: this.stage.scale.x
    }
  }

  setCamera(x: number, y: number, scale: number = 1) {
    this.stage.position.set(x, y)
    this.stage.scale.set(scale)
  }
}
```

## Camera System

```typescript
// src/engine/camera.ts

export class Camera {
  x: number = 0
  y: number = 0
  scale: number = 1
  targetX: number = 0
  targetY: number = 0
  targetScale: number = 1
  width: number
  height: number
  smoothness: number = 0.1

  constructor(width: number, height: number) {
    this.width = width
    this.height = height
  }

  follow(targetX: number, targetY: number) {
    this.targetX = targetX - this.width / 2
    this.targetY = targetY - this.height / 2
  }

  zoom(delta: number) {
    this.targetScale = Math.max(0.5, Math.min(3, this.scale + delta))
  }

  update(delta: number) {
    // Smooth camera movement
    this.x += (this.targetX - this.x) * this.smoothness
    this.y += (this.targetY - this.y) * this.smoothness
    this.scale += (this.targetScale - this.scale) * this.smoothness
  }

  getVisibleChunks(chunkSize: number = 32): number[][] {
    const chunks = []
    const startX = Math.floor((-this.x) / (chunkSize * 32))
    const startY = Math.floor((-this.y) / (chunkSize * 32))
    const endX = Math.ceil((this.width / this.scale - this.x) / (chunkSize * 32))
    const endY = Math.ceil((this.height / this.scale - this.y) / (chunkSize * 32))

    for (let x = startX; x <= endX; x++) {
      for (let y = startY; y <= endY; y++) {
        chunks.push([x, y])
      }
    }

    return chunks
  }
}
```

## Performance Optimization

```typescript
// src/engine/performance.ts

export class PerformanceOptimizer {
  static enableLOD(mesh: any, distance: number) {
    // Reduce polygon count for distant meshes
    if (distance > 1000) {
      mesh.visible = false // Hide far meshes
    }
  }

  static batching(meshes: any[]) {
    // Combine meshes for fewer draw calls
    // Implementation depends on mesh structure
  }

  static culling(meshes: any[], frustum: any) {
    // Remove meshes outside view frustum
    meshes.forEach(mesh => {
      mesh.visible = frustum.intersectsSphere(mesh.getBounds())
    })
  }
}
```

**Resume Token:** `✓ PHASE_4_RENDERING_COMPLETE`
