# Virtual Land World - Frontend

React + Vite frontend for the Virtual Land World platform.

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and npm
- Backend server running on `localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

The app will be available at `http://localhost:3000`

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/       # Reusable UI components
│   │   ├── ProtectedRoute.jsx
│   │   ├── LoadingScreen.jsx
│   │   ├── HUD.jsx
│   │   ├── ChatBox.jsx
│   │   └── ...
│   ├── pages/           # Page components
│   │   ├── LoginPage.jsx
│   │   ├── RegisterPage.jsx
│   │   ├── WorldPage.jsx
│   │   ├── MarketplacePage.jsx
│   │   └── ProfilePage.jsx
│   ├── services/        # API and WebSocket services
│   │   ├── api.js
│   │   └── websocket.js
│   ├── stores/          # Zustand state management
│   │   ├── authStore.js
│   │   ├── worldStore.js
│   │   ├── chatStore.js
│   │   └── marketplaceStore.js
│   ├── hooks/           # Custom React hooks
│   │   ├── useWebSocket.js
│   │   ├── useChunkLoader.js
│   │   └── usePixi.js
│   ├── utils/           # Utility functions
│   │   ├── biomeColors.js
│   │   └── worldHelpers.js
│   ├── styles/          # Global styles
│   │   └── index.css
│   ├── App.jsx          # Main app component
│   └── main.jsx         # Entry point
├── public/              # Static assets
├── index.html
├── vite.config.js
├── tailwind.config.js
└── package.json
```

## 🎨 Technology Stack

- **React 18** - UI framework
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Pixi.js** - 2D WebGL rendering
- **Zustand** - State management
- **React Router** - Routing
- **Axios** - HTTP client
- **React Hot Toast** - Notifications
- **Framer Motion** - Animations

## 🗺️ Features to Implement

### Core Features
- [x] Project structure setup
- [x] API service layer
- [x] WebSocket service
- [x] Authentication store
- [x] World state management
- [ ] Login/Register pages
- [ ] PixiJS world renderer
- [ ] Chunk loading system
- [ ] Camera controls (pan/zoom)
- [ ] Land selection and info
- [ ] Chat UI
- [ ] Marketplace UI
- [ ] Profile page

### Advanced Features
- [ ] WebRTC voice chat
- [ ] Minimap
- [ ] Land coloring based on ownership
- [ ] Real-time presence indicators
- [ ] Notifications system
- [ ] Mobile responsive design
- [ ] Touch controls for mobile
- [ ] Performance optimizations

## 📝 Key Components to Create

### Pages

#### 1. LoginPage.jsx
```jsx
// Login form with email/password
// Links to registration
// Error handling
```

#### 2. RegisterPage.jsx
```jsx
// Registration form
// Password validation
// Auto-login after registration
```

#### 3. WorldPage.jsx
```jsx
// Main game view
// PixiJS canvas
// HUD overlay
// Chat box
// Land info panel
```

#### 4. MarketplacePage.jsx
```jsx
// Listings grid
// Search and filters
// Bidding interface
// Buy now functionality
```

#### 5. ProfilePage.jsx
```jsx
// User stats
// Owned lands list
// Balance and top-up
// Transaction history
```

### Components

#### HUD.jsx
```jsx
// Top bar with user info
// Balance display
// Navigation menu
// Online users count
```

#### ChatBox.jsx
```jsx
// Message list
// Input field
// Typing indicators
// Room switching
```

#### WorldRenderer.jsx
```jsx
// PixiJS Application wrapper
// Chunk rendering
// Camera controls
// Land interaction
```

#### LandInfoPanel.jsx
```jsx
// Selected land details
// Owner information
// Purchase/bid button
// Land actions (fence, transfer)
```

## 🎮 PixiJS World Rendering

### Basic Implementation

```javascript
import * as PIXI from 'pixi.js';

// Create application
const app = new PIXI.Application({
  width: window.innerWidth,
  height: window.innerHeight,
  backgroundColor: 0x1e293b,
  antialias: true,
});

// Container for world
const worldContainer = new PIXI.Container();
app.stage.addChild(worldContainer);

// Render chunk
function renderChunk(chunkData) {
  const { chunk_x, chunk_y, chunk_size, lands } = chunkData;

  lands.forEach((land) => {
    const graphics = new PIXI.Graphics();

    // Get biome color
    const color = getBiomeColor(land.biome);

    // Draw land square
    graphics.beginFill(color);
    graphics.drawRect(
      land.x * LAND_SIZE,
      land.y * LAND_SIZE,
      LAND_SIZE,
      LAND_SIZE
    );
    graphics.endFill();

    worldContainer.addChild(graphics);
  });
}

// Biome colors
const BIOME_COLORS = {
  ocean: 0x1e3a8a,
  beach: 0xfef3c7,
  plains: 0x84cc16,
  forest: 0x166534,
  desert: 0xfdba74,
  mountain: 0x78716c,
  snow: 0xf3f4f6,
};
```

### Camera Controls

```javascript
// Pan
worldContainer.x += deltaX;
worldContainer.y += deltaY;

// Zoom
worldContainer.scale.set(zoom, zoom);

// Center on position
worldContainer.x = -x * zoom + screenWidth / 2;
worldContainer.y = -y * zoom + screenHeight / 2;
```

## 🔌 WebSocket Integration

### Connect and Listen

```javascript
import { wsService } from './services/websocket';

// Connect
await wsService.connect(accessToken);

// Listen for messages
wsService.on('message', (msg) => {
  console.log('Chat message:', msg);
  // Update UI
});

// Join land chat
wsService.joinRoom(landId);

// Send message
wsService.sendMessage(landId, 'Hello world!');

// Update location
wsService.updateLocation(x, y);
```

## 🎨 Styling Guide

### Tailwind CSS Classes

```jsx
// Buttons
<button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
  Click me
</button>

// Cards
<div className="bg-gray-800 rounded-lg p-4 shadow-lg border border-gray-700">
  Content
</div>

// Input
<input className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none" />

// Biome badge
<span className="px-2 py-1 bg-plains text-white text-xs rounded">
  Plains
</span>
```

## 🔧 Environment Variables

Create `.env` file:

```bash
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/api/v1
```

## 📦 State Management

### Auth Store

```javascript
import useAuthStore from './stores/authStore';

const { user, login, logout } = useAuthStore();

// Login
await login(email, password);

// Access user
console.log(user.username, user.balance_bdt);

// Logout
await logout();
```

### World Store

```javascript
import useWorldStore from './stores/worldStore';

const { loadChunk, camera, setCamera } = useWorldStore();

// Load chunk
await loadChunk(0, 0);

// Move camera
setCamera(100, 100, 1.5);
```

## 🚧 Development Tips

### Hot Reload
Vite provides fast HMR. Changes will reflect immediately.

### Debugging
- Use React DevTools for component inspection
- Use Redux DevTools for Zustand (with middleware)
- Console logs in WebSocket service for real-time debugging

### Performance
- Use `React.memo()` for expensive components
- Implement chunk unloading for distant chunks
- Use PixiJS Sprite pooling for many lands
- Debounce camera movement updates

## 📚 Resources

- [PixiJS Documentation](https://pixijs.com/)
- [React Documentation](https://react.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Zustand](https://github.com/pmndrs/zustand)
- [Vite](https://vitejs.dev/)

## 🐛 Common Issues

### WebSocket Connection Failed
- Ensure backend is running
- Check VITE_WS_URL in .env
- Verify JWT token is valid

### Chunks Not Loading
- Check network tab for API errors
- Verify chunk coordinates are correct
- Check backend logs

### Performance Issues
- Reduce visible chunk radius
- Implement chunk culling
- Use PixiJS ParticleContainer for static lands

## 🎯 Next Steps

1. Implement Login/Register pages
2. Create WorldRenderer component with PixiJS
3. Build chunk loading system
4. Add camera controls
5. Create HUD and ChatBox
6. Implement marketplace UI
7. Add WebRTC voice chat
8. Mobile optimization

## 📄 License

Same as parent project.
