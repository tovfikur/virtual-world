/**
 * World Store
 * Manages world state, chunks, and camera
 */

import { create } from 'zustand';
import { chunksAPI, chatAPI } from '../services/api';

const useWorldStore = create((set, get) => ({
  // State
  chunks: new Map(), // Map<"x_y", chunkData>
  loadingChunks: new Set(), // Set<"x_y">
  chunkQueue: [], // Queue of chunks to load
  isLoadingBatch: false, // Flag to prevent concurrent batch loading
  camera: {
    x: 0,
    y: 0,
    zoom: 0.5,
  },
  selectedLand: null,
  selectedLands: [], // Array of selected lands for multi-select
  hoveredLand: null,
  // UI state for multi-select panel (collapsed by default)
  isMultiPanelExpanded: false,
  focusTarget: null,
  multiSelectMode: false, // Toggle for multi-select mode
  unreadMessagesByLand: {}, // Map of land_id -> unread count

  // World info
  worldSeed: null,
  chunkSize: 32,
  batchSize: 12, // Number of chunks to load per batch (higher to fill viewport quickly)

  // Actions
  loadChunk: async (chunkX, chunkY) => {
    const chunkId = `${chunkX}_${chunkY}`;
    const { chunks, loadingChunks } = get();

    // Skip if already loaded or loading
    if (chunks.has(chunkId) || loadingChunks.has(chunkId)) {
      return chunks.get(chunkId);
    }

    // Mark as loading
    set((state) => ({
      loadingChunks: new Set([...state.loadingChunks, chunkId]),
    }));

    try {
      const response = await chunksAPI.getChunk(chunkX, chunkY, get().chunkSize);
      const chunkData = response.data;

      // Store chunk
      set((state) => {
        const newChunks = new Map(state.chunks);
        newChunks.set(chunkId, chunkData);

        const newLoading = new Set(state.loadingChunks);
        newLoading.delete(chunkId);

        return {
          chunks: newChunks,
          loadingChunks: newLoading,
        };
      });

      return chunkData;
    } catch (error) {
      console.error(`Failed to load chunk ${chunkId}:`, error);

      // Remove from loading
      set((state) => {
        const newLoading = new Set(state.loadingChunks);
        newLoading.delete(chunkId);
        return { loadingChunks: newLoading };
      });

      return null;
    }
  },

  loadChunksBatch: async (chunkCoords) => {
    try {
      const response = await chunksAPI.getChunksBatch(chunkCoords, get().chunkSize);
      const { chunks: chunksData } = response.data;

      // Store all chunks
      set((state) => {
        const newChunks = new Map(state.chunks);
        chunksData.forEach((chunk) => {
          newChunks.set(chunk.chunk_id, chunk);
        });
        return { chunks: newChunks };
      });

      return chunksData;
    } catch (error) {
      console.error('Failed to load chunks batch:', error);
      return [];
    }
  },

  // Load chunks sequentially in batches (only if in viewport)
  loadChunksSequentially: async (chunkCoordsList, viewportWidth, viewportHeight) => {
    const { batchSize, chunks, loadingChunks } = get();

    // Filter out already loaded or loading chunks
    const chunksToLoad = chunkCoordsList.filter(([cx, cy]) => {
      const chunkId = `${cx}_${cy}`;
      return !chunks.has(chunkId) && !loadingChunks.has(chunkId);
    });

    if (chunksToLoad.length === 0) {
      return;
    }

    console.log(`📦 Sequential loading: ${chunksToLoad.length} chunks in batches of ${batchSize}`);

    // Prevent concurrent batch loading
    if (get().isLoadingBatch) {
      console.log('⏳ Already loading a batch, queuing chunks...');
      set({ chunkQueue: [...get().chunkQueue, ...chunksToLoad.map(c => ({ coords: c, viewport: { width: viewportWidth, height: viewportHeight } }))] });
      return;
    }

    set({ isLoadingBatch: true });

    let loadedCount = 0;
    let failedCount = 0;
    let skippedCount = 0;

    // Process chunks in batches sequentially
    for (let i = 0; i < chunksToLoad.length; i += batchSize) {
      const batch = chunksToLoad.slice(i, i + batchSize);
      const batchNumber = Math.floor(i / batchSize) + 1;
      const totalBatches = Math.ceil(chunksToLoad.length / batchSize);

      // Load the entire batch (trust initial visible list to be correct enough)
      console.log(`🔄 Loading batch ${batchNumber}/${totalBatches} (${batch.length} chunks)...`);

      // Mark batch as loading
      set((state) => ({
        loadingChunks: new Set([
          ...state.loadingChunks,
          ...batch.map(([cx, cy]) => `${cx}_${cy}`)
        ])
      }));

      const batchPromises = batch.map(async ([cx, cy]) => {
        const chunkId = `${cx}_${cy}`;
        try {
          const response = await chunksAPI.getChunk(cx, cy, get().chunkSize);
          const chunkData = response.data;

          // Store chunk immediately
          set((state) => {
            const newChunks = new Map(state.chunks);
            newChunks.set(chunkId, chunkData);

            const newLoading = new Set(state.loadingChunks);
            newLoading.delete(chunkId);

            return {
              chunks: newChunks,
              loadingChunks: newLoading,
            };
          });

          loadedCount++;
          return { success: true, chunkId };
        } catch (error) {
          console.error(`❌ Failed to load chunk ${chunkId}:`, error.message);

          // Remove from loading on error
          set((state) => {
            const newLoading = new Set(state.loadingChunks);
            newLoading.delete(chunkId);
            return { loadingChunks: newLoading };
          });

          failedCount++;
          return { success: false, chunkId };
        }
      });

      // WAIT for this entire batch to complete before proceeding
      await Promise.all(batchPromises);

      console.log(`✅ Batch ${batchNumber}/${totalBatches} complete (Loaded: ${loadedCount}, Failed: ${failedCount})`);

      // Small delay between batches to avoid overwhelming the server
      if (i + batchSize < chunksToLoad.length) {
        await new Promise(resolve => setTimeout(resolve, 30));
      }
    }

    set({ isLoadingBatch: false });
    console.log(`🎉 Sequential loading complete! Loaded: ${loadedCount}, Failed: ${failedCount}, Skipped: ${skippedCount}`);

    // Process queued chunks if any, filtering by current viewport
    const queue = get().chunkQueue;
    if (queue.length > 0) {
      console.log(`📋 Processing ${queue.length} queued chunks...`);

      // Filter queue to only include chunks still in viewport
      const currentVisibleChunks = get().getVisibleChunks(viewportWidth, viewportHeight);
      const visibleQueuedChunks = queue.filter(item => {
        const [cx, cy] = item.coords;
        return currentVisibleChunks.some(([vcx, vcy]) => vcx === cx && vcy === cy);
      });

      const removedFromQueue = queue.length - visibleQueuedChunks.length;
      if (removedFromQueue > 0) {
        console.log(`🗑️  Removed ${removedFromQueue} chunks from queue (no longer visible)`);
      }

      set({ chunkQueue: [] });

      if (visibleQueuedChunks.length > 0) {
        console.log(`📋 Loading ${visibleQueuedChunks.length} queued visible chunks...`);
        get().loadChunksSequentially(visibleQueuedChunks.map(item => item.coords), viewportWidth, viewportHeight);
      }
    }
  },

  // Update batch size
  setBatchSize: (size) => {
    set({ batchSize: Math.max(1, Math.min(20, size)) }); // Between 1 and 20
  },

  getChunk: (chunkX, chunkY) => {
    const chunkId = `${chunkX}_${chunkY}`;
    return get().chunks.get(chunkId);
  },

  getLandAt: (x, y) => {
    const { chunkSize } = get();
    const chunkX = Math.floor(x / chunkSize);
    const chunkY = Math.floor(y / chunkSize);
    const chunk = get().getChunk(chunkX, chunkY);

    if (!chunk) return null;

    // Find land in chunk
    const localX = x - chunkX * chunkSize;
    const localY = y - chunkY * chunkSize;
    const index = localY * chunkSize + localX;

    return chunk.lands[index];
  },

  // Camera
  setCamera: (x, y, zoom) => {
    set((state) => ({
      camera: {
        x: x !== undefined ? x : state.camera.x,
        y: y !== undefined ? y : state.camera.y,
        zoom: zoom !== undefined ? zoom : state.camera.zoom,
      },
    }));
  },

  moveCamera: (dx, dy) => {
    set((state) => ({
      camera: {
        ...state.camera,
        x: state.camera.x + dx,
        y: state.camera.y + dy,
      },
    }));
  },

  zoomCamera: (delta) => {
    set((state) => ({
      camera: {
        ...state.camera,
        zoom: Math.max(0.25, Math.min(4, state.camera.zoom + delta)),
      },
    }));
  },

  // Selection
  setSelectedLand: (land) => {
    set({ selectedLand: land });
  },

  setHoveredLand: (land) => {
    set({ hoveredLand: land });
  },

  // Multi-select actions
  toggleMultiSelectMode: () => {
    set((state) => ({
      multiSelectMode: !state.multiSelectMode,
      selectedLands: !state.multiSelectMode ? [] : state.selectedLands // Clear when disabling
    }));
  },

  // Control multi-select actions panel visibility
  setMultiPanelExpanded: (val) => set({ isMultiPanelExpanded: val }),
  toggleMultiPanelExpanded: () => set((state) => ({ isMultiPanelExpanded: !state.isMultiPanelExpanded })),

  toggleLandSelection: (land) => {
    set((state) => {
      const landKey = `${land.x}_${land.y}`;
      const isSelected = state.selectedLands.some(l => `${l.x}_${l.y}` === landKey);

      if (isSelected) {
        return { selectedLands: state.selectedLands.filter(l => `${l.x}_${l.y}` !== landKey) };
      } else {
        return { selectedLands: [...state.selectedLands, land] };
      }
    });
  },

  clearSelectedLands: () => {
    set({ selectedLands: [], isMultiPanelExpanded: false });
  },

  selectLandsInArea: (startLand, endLand) => {
    const minX = Math.min(startLand.x, endLand.x);
    const maxX = Math.max(startLand.x, endLand.x);
    const minY = Math.min(startLand.y, endLand.y);
    const maxY = Math.max(startLand.y, endLand.y);

    const landsInArea = [];
    for (let x = minX; x <= maxX; x++) {
      for (let y = minY; y <= maxY; y++) {
        const land = get().getLandAt(x, y);
        if (land) {
          landsInArea.push(land);
        }
      }
    }

    set({ selectedLands: landsInArea });
  },

  setFocusTarget: (target) => {
    set({ focusTarget: target });
  },

  clearFocusTarget: () => {
    set({ focusTarget: null });
  },

  // Update a land property in the chunks store (e.g., fenced status)
  updateLandProperty: (x, y, property, value) => {
    const { chunkSize, chunks } = get();
    const chunkX = Math.floor(x / chunkSize);
    const chunkY = Math.floor(y / chunkSize);
    const chunkId = `${chunkX}_${chunkY}`;

    const chunk = chunks.get(chunkId);
    if (!chunk) return; // Chunk not loaded

    // Find the land in the chunk
    const localX = x - chunkX * chunkSize;
    const localY = y - chunkY * chunkSize;
    const index = localY * chunkSize + localX;

    if (index >= 0 && index < chunk.lands.length) {
      // Update the land property
      const newChunks = new Map(chunks);
      const updatedChunk = { ...chunk };
      updatedChunk.lands = [...chunk.lands];
      updatedChunk.lands[index] = {
        ...chunk.lands[index],
        [property]: value
      };
      newChunks.set(chunkId, updatedChunk);
      set({ chunks: newChunks });
    }
  },

  // World info
  loadWorldInfo: async () => {
    try {
      const response = await chunksAPI.getWorldInfo();
      const { seed, default_chunk_size } = response.data;

      set({
        worldSeed: seed,
        chunkSize: default_chunk_size,
      });
    } catch (error) {
      console.error('Failed to load world info:', error);
    }
  },

  // Unread messages
  loadUnreadMessages: async () => {
    try {
      const response = await chatAPI.getUnreadMessages();
      set({ unreadMessagesByLand: response.data.messages_by_land });
    } catch (error) {
      console.error('Failed to load unread messages:', error);
    }
  },

  getUnreadCount: (landId) => {
    const counts = get().unreadMessagesByLand[landId];
    return counts ? counts.unread : 0;
  },

  getReadCount: (landId) => {
    const counts = get().unreadMessagesByLand[landId];
    return counts ? counts.read : 0;
  },

  hasMessages: (landId) => {
    const counts = get().unreadMessagesByLand[landId];
    return counts && (counts.unread > 0 || counts.read > 0);
  },

  // Utilities
  clearChunks: () => {
    set({ chunks: new Map(), loadingChunks: new Set() });
  },

  getVisibleChunks: (viewportWidth, viewportHeight) => {
    const { camera, chunkSize } = get();
    const scale = camera.zoom;
    const LAND_SIZE = 32; // pixels per land parcel (must match WorldRenderer)

    // Calculate visible area in LAND coordinates (not pixels)
    // viewport pixels / (zoom * pixels per land) = lands visible
    const landsVisibleWidth = viewportWidth / (scale * LAND_SIZE);
    const landsVisibleHeight = viewportHeight / (scale * LAND_SIZE);

    // Calculate land coordinate boundaries
    const startLandX = camera.x - landsVisibleWidth / 2;
    const startLandY = camera.y - landsVisibleHeight / 2;
    const endLandX = camera.x + landsVisibleWidth / 2;
    const endLandY = camera.y + landsVisibleHeight / 2;

    // Convert to chunk coordinates
    const startChunkX = Math.floor(startLandX / chunkSize);
    const startChunkY = Math.floor(startLandY / chunkSize);
    const endChunkX = Math.floor(endLandX / chunkSize);
    const endChunkY = Math.floor(endLandY / chunkSize);

    // Generate list of visible chunks ONLY
    const visibleChunks = [];
    for (let cy = startChunkY; cy <= endChunkY; cy++) {
      for (let cx = startChunkX; cx <= endChunkX; cx++) {
        visibleChunks.push([cx, cy]);
      }
    }

    console.log(`📐 Viewport: ${viewportWidth}x${viewportHeight}, Zoom: ${scale.toFixed(2)}, Camera: (${camera.x.toFixed(0)}, ${camera.y.toFixed(0)})`);
    console.log(`📊 Visible area: ${landsVisibleWidth.toFixed(1)}x${landsVisibleHeight.toFixed(1)} lands = ${visibleChunks.length} chunks`);

    return visibleChunks;
  },
}));

export default useWorldStore;
