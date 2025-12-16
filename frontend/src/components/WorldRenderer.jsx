/**
 * World Renderer Component
 * PixiJS-based infinite world renderer with chunk streaming
 */

import { useCallback, useEffect, useRef, useState } from "react";
import * as PIXI from "pixi.js";
import useWorldStore from "../stores/worldStore";
import useAuthStore from "../stores/authStore";
import { getBiomeColor } from "../utils/biomeColors";
import { landsAPI } from "../services/api";

const LAND_SIZE = 32; // pixels per land parcel
const CHUNK_SIZE = 32; // lands per chunk

function WorldRenderer() {
  const canvasRef = useRef(null);
  const appRef = useRef(null);
  const worldContainerRef = useRef(null);
  const landGraphicsRef = useRef(new Map());
  const landLookupRef = useRef(new Map());
  const badgeGraphicsRef = useRef(new Map()); // land_id -> badge graphics
  const ownershipBordersRef = useRef(new Map()); // owner_id -> border graphics
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
  const lastPosInitializedRef = useRef(false);
  const longPressTimerRef = useRef(null);
  const isLongPressingRef = useRef(false);
  const longPressMultiSelectRef = useRef(false);
  const lastSelectedLandKeyRef = useRef(null);
  const isCtrlDownRef = useRef(false);
  const lastToggleRef = useRef({ key: null, ts: 0 });
  const initialCameraAlignedRef = useRef(false);

  const getPointerType = useCallback((event) => {
    if (!event || !event.data) return "mouse";
    return (
      event.data.pointerType || event.data.originalEvent?.pointerType || "mouse"
    );
  }, []);

  const { user } = useAuthStore();

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
    unreadMessagesByLand,
  } = useWorldStore();

  const [viewport, setViewport] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });

  const resetOwnerHighlight = useCallback(() => {
    // Keep ownership borders permanently visible
    // Only clear the highlighted graphics tracking
    highlightedGraphicsRef.current.clear();
    highlightedOwnerRef.current = null;
  }, []);

  const drawOwnershipBorders = useCallback((ownerId, lands, currentUserId) => {
    if (!worldContainerRef.current) return;

    // Remove existing borders for this owner
    const existingBorder = ownershipBordersRef.current.get(ownerId);
    if (existingBorder) {
      worldContainerRef.current.removeChild(existingBorder);
      ownershipBordersRef.current.delete(ownerId);
    }

    // Create a set of owned coordinates for quick lookup
    const ownedSet = new Set(lands.map((l) => `${l.x}_${l.y}`));

    // Create border graphics
    const borderGraphic = new PIXI.Graphics();
    // Green for current user's lands, white for others
    const borderColor = ownerId === currentUserId ? 0x00ff00 : 0xffffff;
    borderGraphic.lineStyle(3, borderColor, 0.8);

    // For each owned land, draw borders on edges that border non-owned land
    lands.forEach((land) => {
      const baseX = land.x * LAND_SIZE;
      const baseY = land.y * LAND_SIZE;

      // Check all 4 edges
      const hasTop = !ownedSet.has(`${land.x}_${land.y - 1}`);
      const hasBottom = !ownedSet.has(`${land.x}_${land.y + 1}`);
      const hasLeft = !ownedSet.has(`${land.x - 1}_${land.y}`);
      const hasRight = !ownedSet.has(`${land.x + 1}_${land.y}`);

      // Draw border lines for external edges
      if (hasTop) {
        borderGraphic.moveTo(baseX, baseY);
        borderGraphic.lineTo(baseX + LAND_SIZE, baseY);
      }
      if (hasBottom) {
        borderGraphic.moveTo(baseX, baseY + LAND_SIZE);
        borderGraphic.lineTo(baseX + LAND_SIZE, baseY + LAND_SIZE);
      }
      if (hasLeft) {
        borderGraphic.moveTo(baseX, baseY);
        borderGraphic.lineTo(baseX, baseY + LAND_SIZE);
      }
      if (hasRight) {
        borderGraphic.moveTo(baseX + LAND_SIZE, baseY);
        borderGraphic.lineTo(baseX + LAND_SIZE, baseY + LAND_SIZE);
      }
    });

    worldContainerRef.current.addChild(borderGraphic);
    ownershipBordersRef.current.set(ownerId, borderGraphic);
  }, []);

  const applyHighlightToGraphic = useCallback((key) => {
    // No longer change appearance - just track
    if (highlightedGraphicsRef.current.has(key)) {
      return true;
    }

    const meta = landLookupRef.current.get(key);
    if (!meta) {
      return false;
    }

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

      // Cache ownership data
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

      // Draw borders around ownership groups
      drawOwnershipBorders(ownerId, ownerData.lands, user?.user_id);
    },
    [applyHighlightToGraphic, resetOwnerHighlight, drawOwnershipBorders, user]
  );

  useEffect(() => {
    const handleKeyDown = (ev) => {
      if (ev.key === "Control" || ev.key === "Meta")
        isCtrlDownRef.current = true;
    };
    const handleKeyUp = (ev) => {
      if (ev.key === "Control" || ev.key === "Meta")
        isCtrlDownRef.current = false;
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, []);
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
        const { graphic, baseX, baseY, baseScaleX, baseScaleY, baseTint } =
          meta;
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

  // Update land graphics when chunk data changes (e.g., fence status)
  useEffect(() => {
    chunks.forEach((chunkData) => {
      chunkData.lands?.forEach((land) => {
        const key = `${land.x}_${land.y}`;
        const meta = landLookupRef.current.get(key);
        if (meta) {
          // Update the baseTint if fenced status changed
          const newBaseTint = land.fenced ? 0xff6666 : 0xffffff;
          if (meta.baseTint !== newBaseTint) {
            meta.baseTint = newBaseTint;
            // Only update tint if not currently highlighted
            if (
              !highlightedGraphicsRef.current.has(key) &&
              !multiSelectHighlightKeysRef.current.has(key)
            ) {
              meta.graphic.tint = newBaseTint;
            }
          }
        }
      });
    });
  }, [chunks]);

  const handleLandHover = useCallback(
    (land) => {
      const key = `${land.x}_${land.y}`;
      currentHoverKeyRef.current = key;

      // If land doesn't have a land_id, it's not owned - skip API call
      if (!land.land_id) {
        ownershipCacheRef.current.set(key, null);
        currentHoverOwnerRef.current = null;
        resetOwnerHighlight();
        return;
      }

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

  // Align camera on first load so origin starts at top-left (preloads the full visible area)
  useEffect(() => {
    if (initialCameraAlignedRef.current) return;
    if (!viewport.width || !viewport.height) return;
    if (camera.x !== 0 || camera.y !== 0) return;

    const targetX = viewport.width / (2 * LAND_SIZE);
    const targetY = viewport.height / (2 * LAND_SIZE);
    setCamera(targetX, targetY, camera.zoom);
    initialCameraAlignedRef.current = true;
  }, [camera, viewport, setCamera]);

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
        setCamera(centerX, centerY, 0.5);
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
        let color = getBiomeColor(land.biome);

        // === SQUARE GRID WORLD ===
        // Simple rectangular layout
        const baseX = land.x * LAND_SIZE;
        const baseY = land.y * LAND_SIZE;

        g.beginFill(color);
        g.drawRect(0, 0, LAND_SIZE, LAND_SIZE);
        g.endFill();

        // Very thin border
        g.lineStyle(0.5, 0x000000, 0.15);
        g.drawRect(0, 0, LAND_SIZE, LAND_SIZE);

        // Position in world
        g.x = baseX;
        g.y = baseY;

        // Apply red tint for fenced lands
        const baseTint = land.fenced ? 0xff6666 : 0xffffff;
        g.tint = baseTint;

        // Badge will be drawn separately later (not on land graphic)
        // This allows updating badges without redrawing land tiles

        const landKey = `${land.x}_${land.y}`;
        landLookupRef.current.set(landKey, {
          graphic: g,
          baseX,
          baseY,
          baseScaleX: g.scale.x,
          baseScaleY: g.scale.y,
          baseTint: baseTint,
        });

        if (focusHighlightKeysRef.current.has(landKey)) {
          applyHighlightToGraphic(landKey);
        }


        // === Interactivity ===
        g.interactive = true;
        // Don't force the canvas cursor to a hand/pointer on desktop ?
        // we want the mouse to move freely unless the user is actively dragging.
        g.buttonMode = false;
        g.cursor = "default";

        g.on("pointerover", () => {
          console.log(`[WORLD] pointerover ${landKey}`);
          g.alpha = 0.8;
          setHoveredLand(land);
          handleLandHover(land);

          // Handle long press multi-select drag
          if (
            longPressMultiSelectRef.current &&
            lastSelectedLandKeyRef.current !== landKey
          ) {
            toggleLandSelection(land);
            lastSelectedLandKeyRef.current = landKey;
          }
        });
        g.on("pointerout", () => {
          g.alpha = 1;
          if (currentHoverKeyRef.current === landKey) {
            currentHoverKeyRef.current = null;
            currentHoverOwnerRef.current = null;
            // Don't reset owner highlight - keep borders permanently visible
          }
          setHoveredLand(null);
        });
        g.on("pointerdown", (event) => {
          console.log(
            `[WORLD] land pointerdown ${landKey}`,
            event?.data?.originalEvent && {
              ctrl: event.data.originalEvent.ctrlKey,
              meta: event.data.originalEvent.metaKey,
              button: event.data.originalEvent.button,
            }
          );
          // Clear any existing long press timer
          if (longPressTimerRef.current) {
            clearTimeout(longPressTimerRef.current);
          }

          const pointerType = getPointerType(event);
          const isMouse = pointerType === "mouse";

          // On desktop: no long-press selection timer; allow normal click handling on pointerup
          if (isMouse) {
            isLongPressingRef.current = false;
            longPressMultiSelectRef.current = false;
            lastSelectedLandKeyRef.current = null;
          } else {
            // Start long press timer (500ms for mobile)
            longPressTimerRef.current = setTimeout(() => {
              // Long press detected
              isLongPressingRef.current = true;
              longPressMultiSelectRef.current = true;
              toggleLandSelection(land);
              lastSelectedLandKeyRef.current = landKey;
            }, 500);
          }
        });
        g.on("pointerup", (event) => {
          console.log(
            `[WORLD] land pointerup ${landKey}`,
            event?.data?.originalEvent && {
              ctrl: event.data.originalEvent.ctrlKey,
              meta: event.data.originalEvent.metaKey,
              button: event.data.originalEvent.button,
            }
          );
          // Clear any pending long-press timer (mobile)
          if (longPressTimerRef.current) {
            clearTimeout(longPressTimerRef.current);
            longPressTimerRef.current = null;
          }

          const pointerType = getPointerType(event);
          const isMouse = pointerType === "mouse";

          // Handle as regular click if not dragging and not a long-press
          if (!isDraggingRef.current && !isLongPressingRef.current) {
            const orig = event?.data?.originalEvent;
            const wantsMultiSelect =
              (orig && (orig.ctrlKey || orig.metaKey)) || multiSelectMode;

            if (wantsMultiSelect) {
              console.log(`[WORLD] toggleLandSelection ${landKey}`);
              toggleLandSelection(land);
              lastToggleRef.current = { key: landKey, ts: Date.now() };
            } else {
              console.log(`[WORLD] setSelectedLand ${landKey}`);
              setSelectedLand(land);
            }
          }

          // Reset long press flags
          isLongPressingRef.current = false;
          longPressMultiSelectRef.current = false;
          lastSelectedLandKeyRef.current = null;
        });
        g.on("pointerupoutside", () => {
          // Clear long press timer if pointer is released outside
          if (longPressTimerRef.current) {
            clearTimeout(longPressTimerRef.current);
            longPressTimerRef.current = null;
          }

          // Reset long press flags
          isLongPressingRef.current = false;
          longPressMultiSelectRef.current = false;
          lastSelectedLandKeyRef.current = null;
        });

        chunkContainer.addChild(g);
      });

      // Draw badges for lands in this chunk
      chunkData.lands.forEach((land) => {
        if (land.land_id && unreadMessagesByLand[land.land_id]) {
          const messageCounts = unreadMessagesByLand[land.land_id];
          const hasUnread = messageCounts.unread > 0;
          const hasRead = messageCounts.read > 0;

          if (hasUnread || hasRead) {
            const baseX = land.x * LAND_SIZE;
            const baseY = land.y * LAND_SIZE;

            const badge = new PIXI.Graphics();
            const badgeSize = LAND_SIZE * 0.3;
            const badgeX = badgeSize / 2 + LAND_SIZE - badgeSize - 2;
            const badgeY = badgeSize / 2 + 2;

            // Badge color: Red for unread, Green for read only
            const badgeColor = hasUnread ? 0xff4444 : 0x44ff44;

            badge.beginFill(badgeColor);
            badge.drawCircle(0, 0, badgeSize / 2);
            badge.endFill();

            // Badge border (white outline)
            badge.lineStyle(1, 0xffffff, 1);
            badge.drawCircle(0, 0, badgeSize / 2);
            badge.lineStyle(0);

            // Position badge in world coordinates
            badge.x = baseX + badgeX;
            badge.y = baseY + badgeY;

            chunkContainer.addChild(badge);
            badgeGraphicsRef.current.set(land.land_id, { badge, chunkId });
          }
        }
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
    unreadMessagesByLand,
  ]);

  // Update message badges when unread messages change
  useEffect(() => {
    if (!worldContainerRef.current || landGraphicsRef.current.size === 0)
      return;

    console.log(
      `Updating badges (currently ${badgeGraphicsRef.current.size} badges)`
    );

    // Remove all existing badges
    badgeGraphicsRef.current.forEach(({ badge, chunkId }) => {
      const chunkContainer = landGraphicsRef.current.get(chunkId);
      if (chunkContainer && chunkContainer.children.includes(badge)) {
        chunkContainer.removeChild(badge);
      }
    });
    badgeGraphicsRef.current.clear();

    // Redraw badges for all lands with messages
    Object.entries(unreadMessagesByLand).forEach(([landId, messageCounts]) => {
      const hasUnread = messageCounts.unread > 0;
      const hasRead = messageCounts.read > 0;

      if (hasUnread || hasRead) {
        // Find the land in rendered chunks
        chunks.forEach((chunkData, chunkId) => {
          const land = chunkData.lands.find((l) => l.land_id === landId);
          if (land) {
            const chunkContainer = landGraphicsRef.current.get(chunkId);
            if (chunkContainer) {
              const baseX = land.x * LAND_SIZE;
              const baseY = land.y * LAND_SIZE;

              const badge = new PIXI.Graphics();
              const badgeSize = LAND_SIZE * 0.3;
              const badgeX = badgeSize / 2 + LAND_SIZE - badgeSize - 2;
              const badgeY = badgeSize / 2 + 2;

              // Badge color: Red for unread, Green for read only
              const badgeColor = hasUnread ? 0xff4444 : 0x44ff44;

              badge.beginFill(badgeColor);
              badge.drawCircle(0, 0, badgeSize / 2);
              badge.endFill();

              // Badge border (white outline)
              badge.lineStyle(1, 0xffffff, 1);
              badge.drawCircle(0, 0, badgeSize / 2);
              badge.lineStyle(0);

              // Position badge in world coordinates
              badge.x = baseX + badgeX;
              badge.y = baseY + badgeY;

              chunkContainer.addChild(badge);
              badgeGraphicsRef.current.set(landId, { badge, chunkId });
            }
          }
        });
      }
    });

    console.log(`✓ Updated ${badgeGraphicsRef.current.size} badges`);
  }, [unreadMessagesByLand, chunks]);

  // Camera controls - Pan
  useEffect(() => {
    if (!appRef.current) return;

    const app = appRef.current;

    const onPointerDown = (e) => {
      // Only start tracking pointer origin for left-button (primary) presses.
      // Ignore synthetic or non-primary buttons which can cause an immediate "grab" on load.
      const orig = e?.data?.originalEvent;
      console.log("[WORLD] stage pointerdown", {
        hasOriginal: !!orig,
        orig: orig && {
          ctrl: orig.ctrlKey,
          meta: orig.metaKey,
          button: orig.button,
        },
      });
      if (orig && typeof orig.button !== "undefined" && orig.button !== 0) {
        return;
      }

      lastPosRef.current = { x: e.data.global.x, y: e.data.global.y };
      lastPosInitializedRef.current = true;
    };

    const onPointerMove = (e) => {
      // Don't pan camera if in long press multi-select mode
      if (longPressMultiSelectRef.current) {
        return;
      }

      // If we haven't seen a pointerdown for this pointer yet, initialize
      // the lastPos to avoid huge initial deltas that trigger unwanted panning.
      if (!lastPosInitializedRef.current) {
        lastPosRef.current = { x: e.data.global.x, y: e.data.global.y };
        return;
      }

      const dx = e.data.global.x - lastPosRef.current.x;
      const dy = e.data.global.y - lastPosRef.current.y;

      // Only set dragging to true if moved more than 5 pixels
      if (!isDraggingRef.current && (Math.abs(dx) > 5 || Math.abs(dy) > 5)) {
        isDraggingRef.current = true;

        // Cancel long press timer if user is dragging to pan the camera
        if (longPressTimerRef.current) {
          clearTimeout(longPressTimerRef.current);
          longPressTimerRef.current = null;
        }
      }

      if (!isDraggingRef.current) return;

      moveCamera(
        -dx / (camera.zoom * LAND_SIZE),
        -dy / (camera.zoom * LAND_SIZE)
      );

      lastPosRef.current = { x: e.data.global.x, y: e.data.global.y };
    };

    const onPointerUp = (e) => {
      const orig = e?.data?.originalEvent;
      console.log("[WORLD] stage pointerup", {
        hasOriginal: !!orig,
        orig: orig && {
          ctrl: orig.ctrlKey,
          meta: orig.metaKey,
          button: orig.button,
        },
      });
      // If we didn't drag (a click/tap) and not during a long-press,
      // allow Ctrl/Meta+Click to toggle selection at stage level.
      if (!isDraggingRef.current && !isLongPressingRef.current) {
        try {
          const orig = e?.data?.originalEvent;
          const isMouse = getPointerType(e) === "mouse";
          const wantsMultiSelect =
            isCtrlDownRef.current ||
            (orig && (orig.ctrlKey || orig.metaKey)) ||
            multiSelectMode;

          if (wantsMultiSelect && isMouse) {
            // Compute world land coordinates from screen global coords
            const gx = e.data.global.x;
            const gy = e.data.global.y;
            const worldX =
              camera.x + (gx - viewport.width / 2) / (camera.zoom * LAND_SIZE);
            const worldY =
              camera.y + (gy - viewport.height / 2) / (camera.zoom * LAND_SIZE);
            const lx = Math.floor(worldX);
            const ly = Math.floor(worldY);
            const land = getLandAt(lx, ly);
            if (land) {
              const computedKey = `${lx}_${ly}`;
              const recent = lastToggleRef.current;
              if (
                !(recent.key === computedKey && Date.now() - recent.ts < 150)
              ) {
                console.log(
                  `[WORLD] stage-level ctrl+click toggle ${computedKey}`
                );
                toggleLandSelection(land);
                lastToggleRef.current = { key: computedKey, ts: Date.now() };
              } else {
                console.log(
                  `[WORLD] stage-level skip double-toggle ${computedKey}`
                );
              }
            }
          }
        } catch (err) {
          // ignore
        }
      }

      isDraggingRef.current = false;
      lastPosInitializedRef.current = false;
    };

    app.stage.interactive = true;
    // Ensure the renderer's canvas doesn't show a forced cursor at startup
    // (PIXI may change it based on interactive children). Keep default until user drags.
    try {
      app.view.style.cursor = "default";
    } catch (err) {
      // ignore
    }
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

  // Cleanup long press timer on unmount
  useEffect(() => {
    return () => {
      if (longPressTimerRef.current) {
        clearTimeout(longPressTimerRef.current);
      }
    };
  }, []);

  return (
    <div
      ref={canvasRef}
      className="absolute inset-0"
      style={{ cursor: isDraggingRef.current ? "grabbing" : "grab" }}
    />
  );
}

export default WorldRenderer;
