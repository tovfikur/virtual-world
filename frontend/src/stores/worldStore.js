/**
 * World Store
 * Manages world state, chunks, and camera
 */

import { create } from 'zustand';
import { chunksAPI } from '../services/api';

const useWorldStore = create((set, get) => ({
  // State
  chunks: new Map(), // Map<"x_y", chunkData>
  loadingChunks: new Set(), // Set<"x_y">
  chunkQueue: [], // Queue of chunks to load
  isLoadingBatch: false, // Flag to prevent concurrent batch loading
  camera: {
    x: 0,
    y: 0,
    zoom: 1,
  },
  selectedLand: null,
  hoveredLand: null,
  focusTarget: null,

  // World info
  worldSeed: null,
  chunkSize: 32,
  batchSize: 5, // Number of chunks to load per batch

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

      // BEFORE loading, check if chunks are still visible
      const visibleChunksInBatch = batch.filter(([cx, cy]) => {
        const visibleChunks = get().getVisibleChunks(viewportWidth, viewportHeight);
        return visibleChunks.some(([vcx, vcy]) => vcx === cx && vcy === cy);
      });

      if (visibleChunksInBatch.length === 0) {
        skippedCount += batch.length;
        console.log(`⏭️  Skipping batch ${batchNumber}/${totalBatches} - all chunks are outside viewport`);
        continue;
      }

      if (visibleChunksInBatch.length < batch.length) {
        skippedCount += batch.length - visibleChunksInBatch.length;
        console.log(`⏭️  Batch ${batchNumber}/${totalBatches}: ${batch.length - visibleChunksInBatch.length} chunks skipped (outside viewport)`);
      }

      console.log(`🔄 Loading batch ${batchNumber}/${totalBatches} (${visibleChunksInBatch.length} visible chunks)...`);

      // Mark only VISIBLE chunks as loading
      set((state) => ({
        loadingChunks: new Set([
          ...state.loadingChunks,
          ...visibleChunksInBatch.map(([cx, cy]) => `${cx}_${cy}`)
        ])
      }));

      // Load only VISIBLE chunks in this batch (wait for ALL to complete)
      const batchPromises = visibleChunksInBatch.map(async ([cx, cy]) => {
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
        await new Promise(resolve => setTimeout(resolve, 100));
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

  setFocusTarget: (target) => {
    set({ focusTarget: target });
  },

  clearFocusTarget: () => {
    set({ focusTarget: null });
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
