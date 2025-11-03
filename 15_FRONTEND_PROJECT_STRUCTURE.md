# Virtual Land World - Frontend Project Structure

## Project Directory Layout

```
virtualworld-frontend/
├── src/
│   ├── main.ts                          # Application entry point
│   ├── app.ts                           # Main App class
│   ├── config.ts                        # Configuration
│   │
│   ├── engine/
│   │   ├── renderer.ts                  # PixiJS renderer
│   │   ├── camera.ts                    # Camera & viewport
│   │   ├── chunk-loader.ts              # Chunk streaming
│   │   ├── mesh-generator.ts            # Triangle mesh creation
│   │   └── animation.ts                 # Animations & effects
│   │
│   ├── input/
│   │   ├── keyboard.ts                  # Keyboard input handler
│   │   ├── mouse.ts                     # Mouse input handler
│   │   ├── touch.ts                     # Touch input handler
│   │   └── input-manager.ts             # Unified input handling
│   │
│   ├── services/
│   │   ├── api.ts                       # REST API client
│   │   ├── websocket.ts                 # WebSocket manager
│   │   ├── auth.ts                      # Authentication
│   │   ├── cache.ts                     # Client-side caching
│   │   ├── encryption.ts                # E2EE encryption
│   │   └── rtc.ts                       # WebRTC manager
│   │
│   ├── ui/
│   │   ├── hud.ts                       # HUD overlay
│   │   ├── menu.ts                      # Main menu
│   │   ├── chat.ts                      # Chat interface
│   │   ├── marketplace.ts               # Marketplace UI
│   │   └── modals.ts                    # Modal dialogs
│   │
│   ├── world/
│   │   ├── player.ts                    # Player entity
│   │   ├── world.ts                     # World manager
│   │   └── spatial.ts                   # Spatial queries
│   │
│   ├── styles/
│   │   ├── index.css                    # Tailwind CSS
│   │   └── tailwind.config.js           # Tailwind config
│   │
│   └── utils/
│       ├── logger.ts                    # Logging utility
│       ├── math.ts                      # Math utilities
│       └── performance.ts               # Performance monitoring
│
├── public/
│   ├── index.html                       # Main HTML file
│   ├── favicon.ico
│   └── assets/
│       ├── sprites/
│       └── sounds/
│
├── tests/
│   ├── engine.test.ts
│   ├── chunk-loader.test.ts
│   └── input.test.ts
│
├── package.json
├── tsconfig.json
├── vite.config.ts
├── webpack.config.js                    # Alternative bundler
└── README.md
```

## Package.json

```json
{
  "name": "virtualworld-frontend",
  "version": "1.0.0",
  "description": "Virtual Land World - Frontend",
  "type": "module",
  "main": "src/main.ts",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest",
    "lint": "eslint src",
    "format": "prettier --write src"
  },
  "dependencies": {
    "pixi.js": "^7.3.0",
    "axios": "^1.6.0",
    "pydantic": "^2.0.0",
    "socket.io-client": "^4.7.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "@vitejs/plugin-vue": "^5.0.0",
    "tailwindcss": "^3.3.0",
    "vitest": "^1.0.0",
    "eslint": "^8.54.0",
    "prettier": "^3.1.0"
  }
}
```

## TypeScript Configuration

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "noImplicitAny": true,
    "noImplicitThis": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"],
      "@components/*": ["src/components/*"],
      "@services/*": ["src/services/*"],
      "@utils/*": ["src/utils/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

## Vite Configuration

```typescript
// vite.config.ts

import { defineConfig } from 'vite'
import path from 'path'

export default defineConfig({
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true
      }
    }
  },
  build: {
    target: 'esnext',
    outDir: 'dist',
    sourcemap: false,
    minify: 'terser',
    chunkSizeWarningLimit: 500
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
})
```

## Main Application Entry Point

```typescript
// src/main.ts

import { Application } from './app'
import { Config } from './config'

// Load configuration
const config = new Config()

// Initialize application
const app = new Application(config)

// Start game loop
app.start()

// Handle global errors
window.addEventListener('error', (event) => {
  console.error('Global error:', event.error)
  app.showErrorMessage('An error occurred. Please refresh the page.')
})

window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled rejection:', event.reason)
})
```

## Application Class

```typescript
// src/app.ts

import * as PIXI from 'pixi.js'
import { Renderer } from './engine/renderer'
import { InputManager } from './input/input-manager'
import { APIClient } from './services/api'
import { WebSocketManager } from './services/websocket'
import { UIManager } from './ui/hud'
import { World } from './world/world'
import { Config } from './config'

export class Application {
  private renderer: Renderer
  private inputManager: InputManager
  private apiClient: APIClient
  private wsManager: WebSocketManager
  private uiManager: UIManager
  private world: World
  private animationId: number | null = null
  private fps: number = 0
  private frameCount: number = 0
  private lastTime: number = Date.now()

  constructor(private config: Config) {
    // Initialize renderer
    this.renderer = new Renderer(config.game.width, config.game.height)
    document.body.appendChild(this.renderer.app.view as any)

    // Initialize managers
    this.inputManager = new InputManager()
    this.apiClient = new APIClient(config.api)
    this.wsManager = new WebSocketManager(config.api.wsUrl)
    this.uiManager = new UIManager()
    this.world = new World(this.renderer.app)

    this.setupEventListeners()
  }

  private setupEventListeners() {
    // Handle window resize
    window.addEventListener('resize', () => {
      this.renderer.resize(window.innerWidth, window.innerHeight)
    })

    // Handle visibility change
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.pause()
      } else {
        this.resume()
      }
    })
  }

  public async start() {
    try {
      // Load user session
      const user = await this.apiClient.getCurrentUser()
      this.uiManager.updateUserInfo(user)

      // Connect WebSocket
      await this.wsManager.connect(user.user_id)

      // Start game loop
      this.gameLoop()

      console.log('Application started')
    } catch (error) {
      console.error('Failed to start application:', error)
      this.showErrorMessage('Failed to initialize. Please try again.')
    }
  }

  private gameLoop = () => {
    // Update FPS
    const now = Date.now()
    const delta = (now - this.lastTime) / 1000
    this.lastTime = now

    this.frameCount++
    if (this.frameCount % 60 === 0) {
      this.fps = Math.round(1 / delta)
      this.uiManager.updateFPS(this.fps)
    }

    // Update world
    this.world.update(delta)

    // Handle input
    const input = this.inputManager.getInput()
    this.world.handleInput(input)

    // Render
    this.renderer.render()

    // Next frame
    this.animationId = requestAnimationFrame(this.gameLoop)
  }

  public pause() {
    if (this.animationId !== null) {
      cancelAnimationFrame(this.animationId)
      this.animationId = null
    }
  }

  public resume() {
    if (this.animationId === null) {
      this.gameLoop()
    }
  }

  public showErrorMessage(message: string) {
    this.uiManager.showModal('Error', message, ['OK'])
  }
}
```

## Tailwind Configuration

```javascript
// tailwind.config.js

module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#1A5490',
        secondary: '#2d5016',
        danger: '#dc2626',
      },
      spacing: {
        'safe-top': 'env(safe-area-inset-top)',
        'safe-right': 'env(safe-area-inset-right)',
        'safe-bottom': 'env(safe-area-inset-bottom)',
        'safe-left': 'env(safe-area-inset-left)',
      },
    },
  },
  plugins: [],
}
```

## Build Output

```
dist/
├── index.html                   # Generated HTML
├── assets/
│   ├── main-[hash].js          # Main bundle
│   ├── chunk-[hash].js         # Code-split chunks
│   └── style-[hash].css        # CSS bundle
└── favicon.ico
```

## Development Server Setup

```bash
# Install dependencies
npm install

# Start development server (http://localhost:3000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run tests
npm test

# Lint code
npm run lint

# Format code
npm run format
```

## Environment Configuration

```typescript
// src/config.ts

export interface Config {
  game: {
    width: number
    height: number
    targetFPS: number
  }
  api: {
    baseUrl: string
    wsUrl: string
    timeout: number
  }
  cache: {
    chunkTTL: number
    maxChunks: number
  }
  rendering: {
    quality: 'low' | 'medium' | 'high'
    antialiasing: boolean
  }
}

export class Config {
  game = {
    width: window.innerWidth,
    height: window.innerHeight,
    targetFPS: 60,
  }

  api = {
    baseUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
    wsUrl: import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws',
    timeout: 10000,
  }

  cache = {
    chunkTTL: 3600000, // 1 hour
    maxChunks: 25, // 5x5 grid
  }

  rendering = {
    quality: 'high',
    antialiasing: true,
  }
}
```

## Performance Monitoring

```typescript
// src/utils/performance.ts

export class PerformanceMonitor {
  private metrics: Map<string, number[]> = new Map()

  start(label: string) {
    performance.mark(`${label}-start`)
  }

  end(label: string) {
    performance.mark(`${label}-end`)
    performance.measure(label, `${label}-start`, `${label}-end`)

    const measure = performance.getEntriesByName(label)[0]
    if (!this.metrics.has(label)) {
      this.metrics.set(label, [])
    }
    this.metrics.get(label)!.push(measure.duration)
  }

  getStats(label: string) {
    const values = this.metrics.get(label) || []
    if (values.length === 0) return null

    return {
      min: Math.min(...values),
      max: Math.max(...values),
      avg: values.reduce((a, b) => a + b) / values.length,
      count: values.length,
    }
  }
}

export const performanceMonitor = new PerformanceMonitor()
```

**Resume Token:** `✓ PHASE_4_STRUCTURE_COMPLETE`
