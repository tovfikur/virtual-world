# Virtual Land World - Camera & Movement System

## Player Controller

```typescript
// src/world/player.ts

export class Player {
  x: number = 0
  y: number = 0
  vx: number = 0
  vy: number = 0
  speed: number = 200 // pixels per second
  sprite: any

  update(delta: number, input: Input) {
    // Handle input
    if (input.up || input.w) this.vy = -this.speed
    if (input.down || input.s) this.vy = this.speed
    if (input.left || input.a) this.vx = -this.speed
    if (input.right || input.d) this.vx = this.speed

    if (!input.up && !input.down && !input.w && !input.s) this.vy = 0
    if (!input.left && !input.right && !input.a && !input.d) this.vx = 0

    // Update position
    this.x += this.vx * delta
    this.y += this.vy * delta

    // Update sprite
    if (this.sprite) {
      this.sprite.position.set(this.x, this.y)
      if (this.vx !== 0 || this.vy !== 0) {
        this.sprite.rotation = Math.atan2(this.vy, this.vx)
      }
    }
  }

  getChunkCoordinates() {
    return {
      x: Math.floor(this.x / 1024),
      y: Math.floor(this.y / 1024)
    }
  }
}
```

## Input Management

```typescript
// src/input/input-manager.ts

export interface Input {
  up: boolean
  down: boolean
  left: boolean
  right: boolean
  w: boolean
  a: boolean
  s: boolean
  d: boolean
  space: boolean
  mouseX: number
  mouseY: number
  mouseDown: boolean
  touches: Touch[]
}

export class InputManager {
  private input: Input = {
    up: false,
    down: false,
    left: false,
    right: false,
    w: false,
    a: false,
    s: false,
    d: false,
    space: false,
    mouseX: 0,
    mouseY: 0,
    mouseDown: false,
    touches: []
  }

  constructor() {
    this.setupKeyboardListeners()
    this.setupMouseListeners()
    this.setupTouchListeners()
  }

  private setupKeyboardListeners() {
    document.addEventListener('keydown', (e) => {
      switch (e.key.toLowerCase()) {
        case 'arrowup': this.input.up = true; break
        case 'arrowdown': this.input.down = true; break
        case 'arrowleft': this.input.left = true; break
        case 'arrowright': this.input.right = true; break
        case 'w': this.input.w = true; break
        case 'a': this.input.a = true; break
        case 's': this.input.s = true; break
        case 'd': this.input.d = true; break
        case ' ': this.input.space = true; break
      }
    })

    document.addEventListener('keyup', (e) => {
      switch (e.key.toLowerCase()) {
        case 'arrowup': this.input.up = false; break
        case 'arrowdown': this.input.down = false; break
        case 'arrowleft': this.input.left = false; break
        case 'arrowright': this.input.right = false; break
        case 'w': this.input.w = false; break
        case 'a': this.input.a = false; break
        case 's': this.input.s = false; break
        case 'd': this.input.d = false; break
        case ' ': this.input.space = false; break
      }
    })
  }

  private setupMouseListeners() {
    document.addEventListener('mousemove', (e) => {
      this.input.mouseX = e.clientX
      this.input.mouseY = e.clientY
    })

    document.addEventListener('mousedown', () => {
      this.input.mouseDown = true
    })

    document.addEventListener('mouseup', () => {
      this.input.mouseDown = false
    })
  }

  private setupTouchListeners() {
    document.addEventListener('touchstart', (e) => {
      this.input.touches = Array.from(e.touches)
    })

    document.addEventListener('touchmove', (e) => {
      this.input.touches = Array.from(e.touches)
    })

    document.addEventListener('touchend', (e) => {
      this.input.touches = Array.from(e.touches)
    })
  }

  getInput(): Input {
    return { ...this.input }
  }
}
```

## Mobile Touch Controls

```typescript
// src/input/touch.ts

export class TouchController {
  private touchStartX: number = 0
  private touchStartY: number = 0
  private swipeThreshold: number = 50

  handleTouchStart(event: TouchEvent) {
    const touch = event.touches[0]
    this.touchStartX = touch.clientX
    this.touchStartY = touch.clientY
  }

  handleTouchEnd(event: TouchEvent): string | null {
    const touch = event.changedTouches[0]
    const dx = touch.clientX - this.touchStartX
    const dy = touch.clientY - this.touchStartY

    if (Math.abs(dx) > this.swipeThreshold) {
      return dx > 0 ? 'right' : 'left'
    } else if (Math.abs(dy) > this.swipeThreshold) {
      return dy > 0 ? 'down' : 'up'
    }

    return null
  }
}
```

## Viewport Management

```typescript
// src/engine/viewport.ts

export class Viewport {
  width: number
  height: number
  minX: number = -10000
  maxX: number = 10000
  minY: number = -10000
  maxY: number = 10000

  constructor(width: number, height: number) {
    this.width = width
    this.height = height
  }

  clampPosition(x: number, y: number) {
    return {
      x: Math.max(this.minX, Math.min(this.maxX - this.width, x)),
      y: Math.max(this.minY, Math.min(this.maxY - this.height, y))
    }
  }

  getVisibleArea(cameraX: number, cameraY: number, scale: number) {
    return {
      minX: -cameraX / scale,
      maxX: (-cameraX + this.width) / scale,
      minY: -cameraY / scale,
      maxY: (-cameraY + this.height) / scale
    }
  }
}
```

**Resume Token:** `✓ PHASE_4_CAMERA_COMPLETE`
