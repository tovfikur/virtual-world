/**
 * World Renderer Component
 * PixiJS-based infinite world renderer with chunk streaming
 */

import { useCallback, useEffect, useRef, useState } from "react";
import * as PIXI from "pixi.js";
import useWorldStore from "../stores/worldStore";
import { getBiomeColor } from "../utils/biomeColors";
import { landsAPI } from "../services/api";
import toast from "react-hot-toast";

const LAND_SIZE = 32; // pixels per land parcel
const CHUNK_SIZE = 32; // lands per chunk

function WorldRenderer() {
  const canvasRef = useRef(null);
  const appRef = useRef(null);
  const worldContainerRef = useRef(null);
  const landGraphicsRef = useRef(new Map());
  const landLookupRef = useRef(new Map());
  const ownershipCacheRef = useRef(new Map()); // key -> { owner_id, owner_username }
  const ownershipRequestsRef = useRef(new Map()); // key -> active promise
  const ownerLandCacheRef = useRef(new Map()); // owner_id -> { lands, owner_username, fetchedAt }
  const highlightedOwnerRef = useRef(null);
  const highlightedGraphicsRef = useRef(new Map()); // key -> meta
  const currentHoverKeyRef = useRef(null);
  const currentHoverOwnerRef = useRef(null);
  const focusHighlightKeysRef = useRef(new Set());
  const focusHandledIdRef = useRef(null);
  const multiSelectHighlightKeysRef = useRef(new Set());
  const isDraggingRef = useRef(false);
  const lastPosRef = useRef({ x: 0, y: 0 });

  const {
    chunks,
    loadingChunks,
    camera,
    setCamera,
    moveCamera,
    zoomCamera,
    loadChunk,
    loadChunksSequentially,
    batchSize,
    isLoadingBatch,
    setSelectedLand,
    setHoveredLand,
    getVisibleChunks,
    getLandAt,
    focusTarget,
    multiSelectMode,
    selectedLands,
    toggleLandSelection,
  } = useWorldStore();

  const [viewport, setViewport] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });

  const resetOwnerHighlight = useCallback(() => {
    if (highlightedGraphicsRef.current.size === 0) return;

    highlightedGraphicsRef.current.forEach((meta) => {
      const { graphic, baseX, baseY, baseScaleX, baseScaleY, baseTint } = meta;
      graphic.scale.set(baseScaleX, baseScaleY);
      graphic.position.set(baseX, baseY);
      graphic.tint = baseTint;
    });

    highlightedGraphicsRef.current.clear();
    highlightedOwnerRef.current = null;
  }, []);

  const applyHighlightToGraphic = useCallback((key) => {
    if (highlightedGraphicsRef.current.has(key)) {
      return true;
    }

    const meta = landLookupRef.current.get(key);
    if (!meta) {
      return false;
    }

    const { graphic, baseX, baseY, baseScaleX, baseScaleY } = meta;
    const targetScale = 1.08;
    const offsetX = (LAND_SIZE * (targetScale - baseScaleX)) / 2;
    const offsetY = (LAND_SIZE * (targetScale - baseScaleY)) / 2;

    graphic.scale.set(targetScale, targetScale);
    graphic.position.set(baseX - offsetX, baseY - offsetY);
    graphic.tint = 0xfff1a8;

    highlightedGraphicsRef.current.set(key, meta);
    return true;
  }, []);

  const highlightOwner = useCallback(
    async (ownerId) => {
      if (!ownerId) {
        resetOwnerHighlight();
        return;
      }

      if (currentHoverOwnerRef.current !== ownerId) {
        return;
      }

      if (highlightedOwnerRef.current === ownerId) {
        return;
      }

      resetOwnerHighlight();

      let ownerData = ownerLandCacheRef.current.get(ownerId);

      if (!ownerData) {
        try {
          const response = await landsAPI.getOwnerCoordinates(ownerId);
          ownerData = {
            owner_id: ownerId,
            owner_username: response.data.owner_username,
            lands: response.data.lands ?? [],
            fetchedAt: Date.now(),
          };
          ownerLandCacheRef.current.set(ownerId, ownerData);
        } catch (error) {
          console.error("Failed to load owner coordinates", error);
          return;
        }
      }

      highlightedOwnerRef.current = ownerId;

      ownerData.lands.forEach((ownedLand) => {
        const ownedKey = `${ownedLand.x}_${ownedLand.y}`;
        if (!ownershipCacheRef.current.has(ownedKey)) {
          ownershipCacheRef.current.set(ownedKey, {
            owner_id: ownerId,
            owner_username: ownerData.owner_username,
            land_id: ownedLand.land_id,
          });
        }
        applyHighlightToGraphic(ownedKey);
      });
    },
    [applyHighlightToGraphic, resetOwnerHighlight]
  );

  useEffect(() => {
    if (!focusTarget || focusTarget.id === focusHandledIdRef.current) {
      return;
    }

    focusHandledIdRef.current = focusTarget.id;

    resetOwnerHighlight();
    focusHighlightKeysRef.current = new Set();

    if (focusTarget.coordinates?.length) {
      focusTarget.coordinates.forEach((coord) => {
        const key = `${coord.x}_${coord.y}`;
        focusHighlightKeysRef.current.add(key);

        if (focusTarget.ownerId && !ownershipCacheRef.current.has(key)) {
          ownershipCacheRef.current.set(key, {
            owner_id: focusTarget.ownerId,
            owner_username: focusTarget.ownerUsername,
            land_id: coord.land_id,
          });
        }

        applyHighlightToGraphic(key);
      });
    }

    highlightedOwnerRef.current = focusTarget?.ownerId || "__focus__";
  }, [focusTarget, applyHighlightToGraphic, resetOwnerHighlight]);

  // Highlight multi-selected lands
  useEffect(() => {
    // Clear previous multi-select highlights
    multiSelectHighlightKeysRef.current.forEach((key) => {
      const meta = landLookupRef.current.get(key);
      if (meta && !focusHighlightKeysRef.current.has(key)) {
        const { graphic, baseX, baseY, baseScaleX, baseScaleY, baseTint } = meta;
        graphic.scale.set(baseScaleX, baseScaleY);
        graphic.position.set(baseX, baseY);
        graphic.tint = baseTint;
      }
    });
    multiSelectHighlightKeysRef.current.clear();

    // Apply new multi-select highlights
    selectedLands.forEach((land) => {
      const key = `${land.x}_${land.y}`;
      multiSelectHighlightKeysRef.current.add(key);

      const meta = landLookupRef.current.get(key);
      if (meta) {
        const { graphic, baseX, baseY, baseScaleX, baseScaleY } = meta;
        const targetScale = 1.1;
        const offsetX = (LAND_SIZE * (targetScale - baseScaleX)) / 2;
        const offsetY = (LAND_SIZE * (targetScale - baseScaleY)) / 2;

        graphic.scale.set(targetScale, targetScale);
        graphic.position.set(baseX - offsetX, baseY - offsetY);
        graphic.tint = 0x00ffff; // Cyan color for multi-select
      }
    });
  }, [selectedLands]);

  const handleLandHover = useCallback(
    (land) => {
      const key = `${land.x}_${land.y}`;
      currentHoverKeyRef.current = key;

      const cached = ownershipCacheRef.current.get(key);
      if (cached !== undefined) {
        currentHoverOwnerRef.current = cached?.owner_id ?? null;
        if (cached?.owner_id) {
          highlightOwner(cached.owner_id);
        } else {
          resetOwnerHighlight();
        }
        return;
      }

      if (ownershipRequestsRef.current.has(key)) {
        return;
      }

      const request = landsAPI
        .getLandByCoords(land.x, land.y)
        .then((response) => {
          const data = response.data;
          ownershipCacheRef.current.set(key, {
            owner_id: data.owner_id,
            owner_username: data.owner_username,
            land_id: data.land_id,
          });

          if (currentHoverKeyRef.current !== key) {
            return;
          }

          currentHoverOwnerRef.current = data.owner_id ?? null;
          if (data.owner_id) {
            highlightOwner(data.owner_id);
          } else {
            resetOwnerHighlight();
          }
        })
        .catch((error) => {
          if (error.response?.status === 404) {
            ownershipCacheRef.current.set(key, null);
            if (currentHoverKeyRef.current === key) {
              currentHoverOwnerRef.current = null;
              resetOwnerHighlight();
            }
          } else {
            console.error("Failed to fetch land ownership", error);
          }
        })
        .finally(() => {
          ownershipRequestsRef.current.delete(key);
        });

      ownershipRequestsRef.current.set(key, request);
    },
    [highlightOwner, resetOwnerHighlight]
  );

  // Initialize PixiJS application
  useEffect(() => {
    const app = new PIXI.Application({
      width: viewport.width,
      height: viewport.height,
      backgroundColor: 0x1e293b,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    });

    canvasRef.current.appendChild(app.view);
    appRef.current = app;

    // Create world container
    const worldContainer = new PIXI.Container();
    app.stage.addChild(worldContainer);
    worldContainer.sortableChildren = true;
    worldContainerRef.current = worldContainer;

    // Handle window resize
    const handleResize = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      setViewport({ width, height });
      app.renderer.resize(width, height);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      app.destroy(true, { children: true });
    };
  }, []);

  // Update camera transform
  useEffect(() => {
    if (!worldContainerRef.current) return;

    const container = worldContainerRef.current;
    container.scale.set(camera.zoom, camera.zoom);
    container.position.set(
      viewport.width / 2 - camera.x * camera.zoom * LAND_SIZE,
      viewport.height / 2 - camera.y * camera.zoom * LAND_SIZE
    );
  }, [camera, viewport]);

  // Initialize camera to center of first loaded chunks
  useEffect(() => {
    if (chunks.size > 0 && camera.x === 0 && camera.y === 0) {
      // Get first chunk to center camera
      const firstChunk = chunks.values().next().value;
      if (firstChunk) {
        const centerX = firstChunk.chunk_x * CHUNK_SIZE + CHUNK_SIZE / 2;
        const centerY = firstChunk.chunk_y * CHUNK_SIZE + CHUNK_SIZE / 2;
        console.log(
          `Centering camera on chunk ${firstChunk.chunk_id} at (${centerX}, ${centerY})`
        );
        setCamera(centerX, centerY, 1);
      }
    }
  }, [chunks, camera, setCamera]);

  // Load visible chunks SEQUENTIALLY in batches and cull off-screen chunks
  useEffect(() => {
    const visibleChunks = getVisibleChunks(viewport.width, viewport.height);
    const visibleChunkIds = new Set(
      visibleChunks.map(([cx, cy]) => `${cx}_${cy}`)
    );

    // Filter chunks that need to be loaded
    const chunksToLoad = visibleChunks.filter(([cx, cy]) => {
      const chunkId = `${cx}_${cy}`;
      return !chunks.has(chunkId) && !loadingChunks.has(chunkId);
    });

    // Use sequential batch loading instead of loading all at once
    // Pass viewport dimensions so it can check visibility during loading
    if (chunksToLoad.length > 0 && !isLoadingBatch) {
      console.log(
        `🎯 Requesting ${chunksToLoad.length} chunks (batch size: ${batchSize})`
      );
      loadChunksSequentially(chunksToLoad, viewport.width, viewport.height);
    }

    // Hide chunks that are off-screen (visibility culling)
    let visibleCount = 0;
    let hiddenCount = 0;
    landGraphicsRef.current.forEach((chunkContainer, chunkId) => {
      const isVisible = visibleChunkIds.has(chunkId);
      if (chunkContainer.visible !== isVisible) {
        chunkContainer.visible = isVisible;
      }
      if (isVisible) visibleCount++;
      else hiddenCount++;
    });

    // Log stats only when they change significantly
    if (chunksToLoad.length > 0 || hiddenCount > 0) {
      console.log(
        `📊 Chunks - Visible: ${visibleCount}, Hidden: ${hiddenCount}, To Load: ${chunksToLoad.length}`
      );
    }
  }, [camera, viewport]); // eslint-disable-line react-hooks/exhaustive-deps

  // Render chunks
  useEffect(() => {
    if (!worldContainerRef.current) return;

    const container = worldContainerRef.current;
    console.log(
      `Rendering ${chunks.size} chunks, already rendered: ${landGraphicsRef.current.size}`
    );

    chunks.forEach((chunkData, chunkId) => {
      // Skip if already rendered
      if (landGraphicsRef.current.has(chunkId)) return;

      console.log(
        `Rendering new chunk: ${chunkId}, lands: ${chunkData.lands?.length}`
      );

      const chunkContainer = new PIXI.Container();
      chunkContainer.sortableChildren = true;

      chunkData.lands.forEach((land) => {
        const g = new PIXI.Graphics();
        const color = getBiomeColor(land.biome);

        // === SQUARE GRID WORLD ===
        // Simple rectangular layout
        const baseX = land.x * LAND_SIZE;
        const baseY = land.y * LAND_SIZE;

        g.beginFill(color);
        g.drawRect(0, 0, LAND_SIZE, LAND_SIZE);
        g.endFill();

        // Outline / border
        g.lineStyle(1, 0x000000, 0.25);
        g.moveTo(0, 0);
        g.lineTo(LAND_SIZE, 0);
        g.lineTo(LAND_SIZE, LAND_SIZE);
        g.lineTo(0, LAND_SIZE);
        g.closePath();

        // Position in world
        g.x = baseX;
        g.y = baseY;

        const landKey = `${land.x}_${land.y}`;
        landLookupRef.current.set(landKey, {
          graphic: g,
          baseX,
          baseY,
          baseScaleX: g.scale.x,
          baseScaleY: g.scale.y,
          baseTint: g.tint ?? 0xffffff,
        });

        if (focusHighlightKeysRef.current.has(landKey)) {
          applyHighlightToGraphic(landKey);
        }

        // === Interactivity ===
        g.interactive = true;
        g.buttonMode = true;

        g.on("pointerover", () => {
          g.alpha = 0.8;
          setHoveredLand(land);
          handleLandHover(land);
        });
        g.on("pointerout", () => {
          g.alpha = 1;
          if (currentHoverKeyRef.current === landKey) {
            currentHoverKeyRef.current = null;
            currentHoverOwnerRef.current = null;
            resetOwnerHighlight();
            if (focusHighlightKeysRef.current.size > 0) {
              focusHighlightKeysRef.current.forEach((key) => applyHighlightToGraphic(key));
              highlightedOwnerRef.current = focusTarget?.ownerId || "__focus__";
            }
          }
          setHoveredLand(null);
        });
        g.on("pointerdown", (event) => {
          if (!isDraggingRef.current) {
            // Multi-select mode: toggle selection with Ctrl/Cmd key
            if (event.data.originalEvent.ctrlKey || event.data.originalEvent.metaKey || multiSelectMode) {
              const isSelected = selectedLands.some(l => l.x === land.x && l.y === land.y);
              toggleLandSelection(land);
              toast.success(isSelected ? `Deselected (${land.x}, ${land.y})` : `Selected (${land.x}, ${land.y})`);
            } else {
              // Single select mode
              setSelectedLand(land);
              toast.success(`Selected land at (${land.x}, ${land.y})`);
            }
          }
        });

        chunkContainer.addChild(g);
      });

      container.addChild(chunkContainer);
      landGraphicsRef.current.set(chunkId, chunkContainer);
    });
  }, [
    chunks,
    setSelectedLand,
    setHoveredLand,
    handleLandHover,
    resetOwnerHighlight,
    applyHighlightToGraphic,
    focusTarget,
  ]);

  // Camera controls - Pan
  useEffect(() => {
    if (!appRef.current) return;

    const app = appRef.current;

    const onPointerDown = (e) => {
      isDraggingRef.current = true;
      lastPosRef.current = { x: e.data.global.x, y: e.data.global.y };
    };

    const onPointerMove = (e) => {
      if (!isDraggingRef.current) return;

      const dx = e.data.global.x - lastPosRef.current.x;
      const dy = e.data.global.y - lastPosRef.current.y;

      moveCamera(
        -dx / (camera.zoom * LAND_SIZE),
        -dy / (camera.zoom * LAND_SIZE)
      );

      lastPosRef.current = { x: e.data.global.x, y: e.data.global.y };
    };

    const onPointerUp = () => {
      isDraggingRef.current = false;
    };

    app.stage.interactive = true;
    app.stage.on("pointerdown", onPointerDown);
    app.stage.on("pointermove", onPointerMove);
    app.stage.on("pointerup", onPointerUp);
    app.stage.on("pointerupoutside", onPointerUp);

    return () => {
      // Check if stage exists before removing listeners
      if (app.stage) {
        app.stage.off("pointerdown", onPointerDown);
        app.stage.off("pointermove", onPointerMove);
        app.stage.off("pointerup", onPointerUp);
        app.stage.off("pointerupoutside", onPointerUp);
      }
    };
  }, [camera, moveCamera]);

  // Camera controls - Zoom
  useEffect(() => {
    if (!canvasRef.current) return;

    const handleWheel = (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      zoomCamera(delta);
    };

    const canvas = canvasRef.current.querySelector("canvas");
    if (canvas) {
      canvas.addEventListener("wheel", handleWheel, { passive: false });
    }

    return () => {
      if (canvas) {
        canvas.removeEventListener("wheel", handleWheel);
      }
    };
  }, [zoomCamera]);

  return (
    <div
      ref={canvasRef}
      className="absolute inset-0"
      style={{ cursor: isDraggingRef.current ? "grabbing" : "grab" }}
    />
  );
}

export default WorldRenderer;
