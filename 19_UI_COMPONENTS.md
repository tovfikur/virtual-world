# Virtual Land World - UI Components & HUD

## HUD Overlay

```typescript
// src/ui/hud.ts

export class HUD {
  container: PIXI.Container
  fpsText: PIXI.Text
  coordinatesText: PIXI.Text
  balanceText: PIXI.Text
  presenceText: PIXI.Text

  constructor() {
    this.container = new PIXI.Container()

    // FPS Counter
    this.fpsText = new PIXI.Text('FPS: 60', {
      fontSize: 16,
      fill: 0xffffff,
      fontFamily: 'monospace'
    })
    this.fpsText.position.set(10, 10)

    // Coordinates
    this.coordinatesText = new PIXI.Text('(0, 0)', {
      fontSize: 14,
      fill: 0xffffff
    })
    this.coordinatesText.position.set(10, 35)

    // Balance
    this.balanceText = new PIXI.Text('Balance: 0 BDT', {
      fontSize: 14,
      fill: 0x00ff00
    })
    this.balanceText.position.set(10, 60)

    // Presence
    this.presenceText = new PIXI.Text('Players nearby: 0', {
      fontSize: 12,
      fill: 0xffff00
    })
    this.presenceText.position.set(10, 85)

    this.container.addChild(
      this.fpsText,
      this.coordinatesText,
      this.balanceText,
      this.presenceText
    )
  }

  updateFPS(fps: number) {
    this.fpsText.text = `FPS: ${fps}`
  }

  updateCoordinates(x: number, y: number) {
    this.coordinatesText.text = `(${Math.round(x)}, ${Math.round(y)})`
  }

  updateBalance(balance: number) {
    this.balanceText.text = `Balance: ${balance} BDT`
  }

  updatePresence(count: number) {
    this.presenceText.text = `Players nearby: ${count}`
  }

  getContainer(): PIXI.Container {
    return this.container
  }
}
```

## Modal System

```typescript
// src/ui/modals.ts

export class ModalManager {
  private modals: Map<string, Modal> = new Map()
  private container: PIXI.Container

  constructor(container: PIXI.Container) {
    this.container = container
  }

  async showModal(title: string, message: string, buttons: string[]): Promise<string> {
    return new Promise((resolve) => {
      const modal = new Modal(title, message, buttons, (result) => {
        this.container.removeChild(modal.getContainer())
        this.modals.delete(title)
        resolve(result)
      })

      this.modals.set(title, modal)
      this.container.addChild(modal.getContainer())
    })
  }
}

export class Modal {
  container: PIXI.Container
  background: PIXI.Graphics
  titleText: PIXI.Text
  messageText: PIXI.Text
  buttons: ModalButton[] = []

  constructor(
    title: string,
    message: string,
    buttonLabels: string[],
    onClose: (result: string) => void
  ) {
    this.container = new PIXI.Container()

    // Semi-transparent background
    this.background = new PIXI.Graphics()
    this.background.fillStyle(0x000000, 0.7)
    this.background.drawRect(0, 0, window.innerWidth, window.innerHeight)
    this.container.addChild(this.background)

    // Modal box
    const box = new PIXI.Graphics()
    box.fillStyle(0x333333)
    box.drawRect(100, 100, 400, 300)
    this.container.addChild(box)

    // Title
    this.titleText = new PIXI.Text(title, {
      fontSize: 20,
      fill: 0xffffff,
      fontWeight: 'bold'
    })
    this.titleText.position.set(120, 120)
    this.container.addChild(this.titleText)

    // Message
    this.messageText = new PIXI.Text(message, {
      fontSize: 14,
      fill: 0xcccccc,
      wordWrap: true,
      wordWrapWidth: 360
    })
    this.messageText.position.set(120, 160)
    this.container.addChild(this.messageText)

    // Buttons
    buttonLabels.forEach((label, i) => {
      const button = new ModalButton(label, () => {
        onClose(label)
      })
      button.position.set(150 + i * 100, 360)
      this.buttons.push(button)
      this.container.addChild(button.getContainer())
    })
  }

  getContainer(): PIXI.Container {
    return this.container
  }
}

export class ModalButton {
  container: PIXI.Container
  background: PIXI.Graphics
  text: PIXI.Text

  constructor(label: string, onClick: () => void) {
    this.container = new PIXI.Container()
    this.container.interactive = true
    this.container.on('pointerdown', onClick)

    this.background = new PIXI.Graphics()
    this.background.fillStyle(0x0066cc)
    this.background.drawRect(0, 0, 80, 30)
    this.container.addChild(this.background)

    this.text = new PIXI.Text(label, {
      fontSize: 12,
      fill: 0xffffff
    })
    this.text.position.set(10, 8)
    this.container.addChild(this.text)
  }

  getContainer(): PIXI.Container {
    return this.container
  }
}
```

## Chat UI (Tailwind-based)

```html
<!-- public/index.html (chat panel overlay) -->

<div id="chat-panel" class="fixed bottom-4 right-4 w-80 h-96 bg-gray-900 rounded-lg shadow-lg flex flex-col">
  <div class="bg-blue-600 text-white p-4 rounded-t-lg">
    <h3 class="font-bold">Chat</h3>
  </div>

  <div id="chat-messages" class="flex-1 overflow-y-auto p-4 space-y-2">
    <!-- Messages will be inserted here -->
  </div>

  <div class="p-4 border-t border-gray-700">
    <div class="flex gap-2">
      <input
        id="chat-input"
        type="text"
        placeholder="Send message..."
        class="flex-1 bg-gray-800 text-white px-3 py-2 rounded border border-gray-700"
      />
      <button
        id="chat-send"
        class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
      >
        Send
      </button>
    </div>
  </div>
</div>
```

## Marketplace UI (Tailwind-based)

```html
<!-- public/marketplace.html -->

<div class="w-full max-w-4xl mx-auto p-6">
  <h1 class="text-3xl font-bold mb-6">Marketplace</h1>

  <!-- Search & Filter -->
  <div class="mb-6 grid grid-cols-4 gap-4">
    <input
      id="search"
      type="text"
      placeholder="Search by biome..."
      class="col-span-2 px-4 py-2 border rounded-lg"
    />
    <select id="sort" class="px-4 py-2 border rounded-lg">
      <option value="price_asc">Price: Low to High</option>
      <option value="price_desc">Price: High to Low</option>
      <option value="created_at_desc">Newest First</option>
    </select>
    <button class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
      Search
    </button>
  </div>

  <!-- Listings Grid -->
  <div id="listings" class="grid grid-cols-3 gap-6">
    <!-- Listings will be inserted here -->
  </div>
</div>
```

## Responsive Design

```css
/* src/styles/index.css */

@tailwind base;
@tailwind components;
@tailwind utilities;

/* Mobile-first responsive layout */
@media (max-width: 768px) {
  #chat-panel {
    @apply w-full h-1/2 bottom-0 right-0 rounded-none;
  }

  #listings {
    @apply grid-cols-1;
  }

  .hud {
    @apply text-sm;
  }
}

/* Safe area insets for notched devices */
@supports (padding: max(0px)) {
  body {
    padding-left: max(0px, env(safe-area-inset-left));
    padding-right: max(0px, env(safe-area-inset-right));
    padding-top: max(0px, env(safe-area-inset-top));
  }
}
```

**Resume Token:** `✓ PHASE_4_COMPLETE`
