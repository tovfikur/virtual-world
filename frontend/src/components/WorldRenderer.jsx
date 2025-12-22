/**
 * World Renderer Component
 * PixiJS-based infinite world renderer with chunk streaming
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as PIXI from "pixi.js";
import useWorldStore from "../stores/worldStore";
import useAuthStore from "../stores/authStore";
import { getBiomeColor } from "../utils/biomeColors";
import { landsAPI, wsAPI } from "../services/api";
import { wsService } from "../services/websocket";
import { ROCK_SAMPLES, ROCK_SAMPLE_RATE } from "../assets/rockStepSample";
import { WATER_SAMPLE, WATER_SAMPLE_RATE } from "../assets/waterStepSample";
import { BELL_SAMPLE, BELL_SAMPLE_RATE } from "../assets/connectBellSample";

const LAND_SIZE = 32; // pixels per land parcel
const CHUNK_SIZE = 32; // lands per chunk
const TILE_STEP_DURATION = 0.22; // seconds to complete a tile walk
const INPUT_DEADZONE = 0.28; // threshold before we treat input as intentional
const WALK_FREQUENCY = 7; // oscillations per second
const LEG_SWING_MULTIPLIER = 0.18; // portion of tile size used for leg movement
const CAMERA_RECENTER_SPEED = 4.5; // tiles per second when easing camera after jumps

const hslToRgb = (h, s, l) => {
  if (s === 0) {
    const val = Math.round(l * 255);
    return [val, val, val];
  }

  const hue2rgb = (p, q, t) => {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };

  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;

  const r = Math.round(hue2rgb(p, q, h + 1 / 3) * 255);
  const g = Math.round(hue2rgb(p, q, h) * 255);
  const b = Math.round(hue2rgb(p, q, h - 1 / 3) * 255);

  return [r, g, b];
};

const OCCUPANCY_COLOR = 0x2563eb;

const uniqueColorFromString = (input) => {
  const text = input || "guest";
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) - hash + text.charCodeAt(i)) | 0;
  }
  const hue = Math.abs(hash) % 360;
  const [r, g, b] = hslToRgb(hue / 360, 0.58, 0.55);
  return (r << 16) | (g << 8) | b;
};

const snapToTileCenter = (value) => {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }
  return Math.round(value - 0.5) + 0.5;
};

const nearlyEqual = (a, b, epsilon = 1e-3) =>
  typeof a === "number" &&
  typeof b === "number" &&
  Math.abs(a - b) <= epsilon;

const tileKey = (x, y) => `${Math.floor(x)}_${Math.floor(y)}`;

const parseTileKey = (key) => {
  const [tx, ty] = key.split("_").map((v) => Number.parseInt(v, 10));
  return {
    x: Number.isFinite(tx) ? tx : 0,
    y: Number.isFinite(ty) ? ty : 0,
  };
};

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const FOOTSTEP_PROFILES = {
  default: {
    duration: 0.32,
    toneFreq: 90,
    noiseLevel: 0.3,
    textureFreq: 26,
    resonance: 5.5,
    brightness: 0.35,
    gain: 1,
    sampleData: null,
    sampleRate: null,
    sampleGain: 1,
    samplePlaybackRate: 1,
    samplePlaybackVariance: 0.02,
  },
  sand: {
    duration: 0.4,
    toneFreq: 55,
    noiseLevel: 0.55,
    textureFreq: 14,
    resonance: 4.4,
    brightness: 0.25,
  },
  water: {
    sampleData: WATER_SAMPLE,
    sampleRate: WATER_SAMPLE_RATE,
    sampleGain: 0.8,
    samplePlaybackRate: 1,
    samplePlaybackVariance: 0.04,
    duration: 0.55,
    toneFreq: 45,
    noiseLevel: 0.5,
    textureFreq: 9,
    resonance: 4.2,
    brightness: 0.14,
    waterMotion: 0,
    splashFreq: 0,
    dropletChance: 0,
  },
  forest: {
    duration: 0.34,
    toneFreq: 70,
    noiseLevel: 0.45,
    textureFreq: 32,
    resonance: 5.3,
    brightness: 0.28,
  },
  rock: {
    sampleData: ROCK_SAMPLES,
    sampleRate: ROCK_SAMPLE_RATE,
    sampleGain: 0.5,
    samplePlaybackRate: 1.32,
    samplePlaybackVariance: 0.06,
    gain: 0.7,
    duration: 0.19,
    toneFreq: 175,
    noiseLevel: 0.12,
    textureFreq: 72,
    resonance: 2.1,
    brightness: 0.88,
    stoneClack: 0,
    gritLevel: 0,
    stoneEdge: 0,
  },
  snow: {
    duration: 0.42,
    toneFreq: 48,
    noiseLevel: 0.12,
    textureFreq: 10,
    resonance: 6.6,
    brightness: 0.22,
  },
};

const resolveFootstepProfileKey = (biome) => {
  const key = biome?.toLowerCase();
  switch (key) {
    case "ocean":
    case "water":
      return "water";
    case "beach":
    case "desert":
    case "sand":
      return "sand";
    case "forest":
    case "jungle":
      return "forest";
    case "mountain":
    case "rock":
      return "rock";
    case "snow":
    case "ice":
      return "snow";
    default:
      return "default";
  }
};

const FOOTSTEP_CLEAR_RADIUS = 1; // ~3x3 area (Chebyshev <= 1)
const FOOTSTEP_MAX_RADIUS = 50; // ~101x101 tile window (Chebyshev radius)

const calculateFootstepGain = (distance) => {
  if (distance <= FOOTSTEP_CLEAR_RADIUS) {
    return 1;
  }
  if (distance >= FOOTSTEP_MAX_RADIUS) {
    return 0;
  }
  const t =
    (distance - FOOTSTEP_CLEAR_RADIUS) /
    (FOOTSTEP_MAX_RADIUS - FOOTSTEP_CLEAR_RADIUS);
  return Math.pow(1 - t, 1.1);
};

const calculateFootstepPan = (dx, dy) => {
  const planarDistance = Math.max(Math.hypot(dx, dy), 1e-3);
  return clamp(dx / planarDistance, -1, 1);
};

const createSampleBuffer = (
  audioCtx,
  data,
  sourceRate,
  gain = 1
) => {
  if (!audioCtx || !Array.isArray(data) || data.length === 0) {
    return null;
  }
  const targetRate = audioCtx.sampleRate || sourceRate || 44100;
  const srcRate = sourceRate || targetRate;
  const duration = data.length / srcRate;
  const length = Math.max(1, Math.round(duration * targetRate));
  const buffer = audioCtx.createBuffer(1, length, targetRate);
  const channel = buffer.getChannelData(0);

  for (let i = 0; i < length; i += 1) {
    const srcPos = (i / targetRate) * srcRate;
    const idx = Math.floor(srcPos);
    const frac = srcPos - idx;
    const a = data[idx] ?? 0;
    const b = data[idx + 1] ?? 0;
    channel[i] = (a + (b - a) * frac) * gain;
  }

  return buffer;
};

const createFootstepBuffer = (audioCtx, profile = FOOTSTEP_PROFILES.default) => {
  const settings = { ...FOOTSTEP_PROFILES.default, ...profile };
  const {
    duration,
    toneFreq,
    noiseLevel,
    textureFreq,
    resonance,
    brightness,
    waterMotion = 0,
    splashFreq = 0,
    dropletChance = 0,
    stoneClack = 0,
    gritLevel = 0,
    stoneEdge = 0,
    sampleData = null,
    sampleRate: profileSampleRate = null,
    sampleGain = 1,
  } = settings;

  if (sampleData?.length) {
    const normalizedSamples =
      Array.isArray(sampleData[0]) && typeof sampleData[0] !== "number"
        ? sampleData
        : [sampleData];
    const buffers = normalizedSamples
      .map((sample) =>
        createSampleBuffer(
          audioCtx,
          sample,
          profileSampleRate || audioCtx?.sampleRate,
          sampleGain
        )
      )
      .filter(Boolean);
    if (buffers.length === 1) {
      return buffers[0];
    }
    if (buffers.length > 1) {
      return buffers;
    }
  }
  const sampleRate = audioCtx.sampleRate;
  const length = Math.floor(sampleRate * duration);
  const buffer = audioCtx.createBuffer(1, length, sampleRate);
  const channel = buffer.getChannelData(0);

  for (let i = 0; i < length; i += 1) {
    const t = i / length;
    const attack = Math.min(1, t * 4);
    const decay = Math.exp(-resonance * t);
    const envelope = attack * decay;

    const tone =
      Math.sin(2 * Math.PI * toneFreq * (i / sampleRate)) *
      (0.5 + brightness);
    const texture =
      Math.sin(2 * Math.PI * textureFreq * (i / sampleRate)) *
      noiseLevel *
      0.3;
    const noise = (Math.random() * 2 - 1) * noiseLevel;

    const isStoneProfile =
      stoneClack > 0 || gritLevel > 0 || stoneEdge > 0;
    const baseSample = tone + texture + noise;
    let sample = isStoneProfile ? 0 : baseSample;

    if (waterMotion > 0) {
      const splashEnvelope = Math.pow(1 - Math.abs(0.5 - t) * 2, 0.9);
      const ripple =
        Math.sin(
          2 * Math.PI * (textureFreq * 0.38) * (i / sampleRate + t * 0.6)
        ) *
        (Math.sin(t * Math.PI * splashFreq) * 0.5 + 0.5);
      sample += ripple * waterMotion * splashEnvelope;

      if (dropletChance > 0 && Math.random() < dropletChance * envelope) {
        const dropletPhase = Math.sin(
          2 * Math.PI * (textureFreq * 1.4) * (t + Math.random())
        );
        const dropletEnvelope = Math.exp(-24 * Math.random()) * (1 - t * 0.8);
        sample += dropletPhase * 0.7 * dropletEnvelope;
      }
    }

    if (stoneClack > 0) {
      const timeNorm = i / sampleRate;

      // Sharp click
      const clickEnv = Math.exp(-240 * t);
      const click = Math.sin(
        2 * Math.PI * toneFreq * 3.4 * timeNorm
      );

      // Body clack (lower pitched, slightly later)
      const clackEnv = Math.exp(-110 * Math.abs(t - 0.1));
      const clack = Math.sin(
        2 * Math.PI * toneFreq * 0.95 * timeNorm
      );

      // Gritty echo
      const gritEnv = Math.exp(-90 * t);
      const grit =
        (Math.random() * 2 - 1) *
        gritLevel *
        gritEnv;

      let stoneSample =
        click * clickEnv * 0.65 +
        clack * clackEnv * 0.55 +
        grit;

      if (stoneEdge > 0) {
        const edgeEnv = Math.exp(-150 * Math.abs(t - 0.05));
        const edge =
          Math.sin(2 * Math.PI * toneFreq * 4.8 * timeNorm) *
          edgeEnv *
          stoneEdge;
        stoneSample += edge * 0.4;
      }

      const hardGate = Math.exp(-180 * t);
      stoneSample *= hardGate;

      sample += stoneSample * stoneClack;
    }

    if (gritLevel > 0) {
      const grit = (Math.random() * 2 - 1) * gritLevel * (1 - t);
      sample += grit;
    }

    channel[i] = sample * envelope;
  }

  return buffer;
};

const MESSAGE_STATUS_COLORS = {
  unread: 0xff4d4d,
  pending: 0xffc857,
  read: 0x35d687,
  mine: 0xb889ff,
  others: 0x4b5563,
};

const getMessageBadgeColor = (counts = {}, context = {}) => {
  const { isOwner } = context;
  const unread = counts.unread ?? 0;
  const read = counts.read ?? 0;
  const received = counts.received ?? 0;
  const mineUnread = counts.mine_unread ?? counts.mineUnread ?? 0;
  const mineRead = counts.mine_read ?? counts.mineRead ?? 0;
  const mineTotal =
    counts.mine_total ?? counts.mineTotal ?? mineUnread + mineRead;
  const othersTotal =
    counts.others_total ?? counts.othersTotal ?? received ?? 0;

  if (isOwner) {
    if (unread > 0) {
      return MESSAGE_STATUS_COLORS.unread;
    }
    if (read > 0) {
      return MESSAGE_STATUS_COLORS.read;
    }
    if (received > 0) {
      return MESSAGE_STATUS_COLORS.pending;
    }
    return null;
  }

  if (mineTotal > 0) {
    return MESSAGE_STATUS_COLORS.mine;
  }

  if (othersTotal > 0) {
    return MESSAGE_STATUS_COLORS.others;
  }

  return null;
};

const connectSoundGain = 0.75;

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
  const playerContainerRef = useRef(null);
  const playerPartsRef = useRef({ head: null, leftLeg: null, rightLeg: null });
  const playerPositionRef = useRef({ x: 0, y: 0 });
  const playerStepRef = useRef({
    active: false,
    startX: 0,
    startY: 0,
    endX: 0,
    endY: 0,
    elapsed: 0,
    duration: TILE_STEP_DURATION,
  });
  const playerInitializedRef = useRef(false);
  const keyboardStateRef = useRef({
    up: false,
    down: false,
    left: false,
    right: false,
  });
  const keyboardDirectionRef = useRef({ x: 0, y: 0 });
  const touchDirectionRef = useRef({ x: 0, y: 0, active: false });
  const movementDirectionRef = useRef({ x: 0, y: 0 });
  const playerAnimationRef = useRef({ phase: 0 });
  const touchPadPointerIdRef = useRef(null);
  const cameraRef = useRef(null);
  const audioContextRef = useRef(null);
  const footstepBuffersRef = useRef(new Map());
  const [isTouchDevice, setIsTouchDevice] = useState(false);
  const [touchPadVector, setTouchPadVector] = useState({
    x: 0,
    y: 0,
    active: false,
  });
  const [isPlayerReady, setIsPlayerReady] = useState(false);
  const [playerHomeTiles, setPlayerHomeTiles] = useState(null);
  const spawnResolvedRef = useRef(false);
  const lastOwnerIdRef = useRef(null);
  const lastSelectedTileRef = useRef({ x: null, y: null });
  const pendingCenterOnMoveRef = useRef(false);
  const autoCenterRef = useRef(false);
  const playerHeadColorRef = useRef(0xffd7a3);
  const remotePlayersRef = useRef(new Map());
  const pendingRemoteUpdatesRef = useRef(new Map());
  const lastBroadcastRef = useRef({ x: null, y: null, time: 0 });
  const occupancyLayerRef = useRef(null);
  const occupancyIndicatorsRef = useRef(new Map());
  const bellBufferRef = useRef(null);
  const lastTileOccupancyRef = useRef(1);

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

  const getBiomeProfileForCoords = useCallback(
    (worldX, worldY) => {
      if (!Number.isFinite(worldX) || !Number.isFinite(worldY)) {
        return "default";
      }
      const tileX = Math.floor(worldX);
      const tileY = Math.floor(worldY);
      const land = getLandAt(tileX, tileY);
      return resolveFootstepProfileKey(land?.biome);
    },
    [getLandAt]
  );

  const ensureAudioContext = useCallback(() => {
    if (typeof window === "undefined") return null;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return null;
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContextClass();
    }
    const ctx = audioContextRef.current;
    if (ctx.state === "suspended") {
      ctx.resume();
    }
    return ctx;
  }, []);

  useEffect(() => {
    const unlockAudio = () => {
      const ctx = ensureAudioContext();
      if (ctx && ctx.state !== "suspended") {
        window.removeEventListener("pointerdown", unlockAudio);
        window.removeEventListener("keydown", unlockAudio);
      }
    };
    window.addEventListener("pointerdown", unlockAudio);
    window.addEventListener("keydown", unlockAudio);
    return () => {
      window.removeEventListener("pointerdown", unlockAudio);
    window.removeEventListener("keydown", unlockAudio);
    };
  }, [ensureAudioContext]);

  const playFootstepSound = useCallback(
    (worldX, worldY, options = {}) => {
      const { profileKey: requestedProfile = "default", usePanning = true, volume = 1 } = options;
      if (!Number.isFinite(worldX) || !Number.isFinite(worldY)) {
        return;
      }

      const audioCtx = ensureAudioContext();
      if (!audioCtx) return;

      const resolvedProfile =
        requestedProfile && FOOTSTEP_PROFILES[requestedProfile]
          ? requestedProfile
          : "default";
      const profileDefinition =
        FOOTSTEP_PROFILES[resolvedProfile] || FOOTSTEP_PROFILES.default;

      let bufferEntry = footstepBuffersRef.current.get(resolvedProfile);
      if (!bufferEntry) {
        bufferEntry = createFootstepBuffer(
          audioCtx,
          profileDefinition
        );
        footstepBuffersRef.current.set(resolvedProfile, bufferEntry);
      }
      const pickBuffer = () => {
        if (Array.isArray(bufferEntry)) {
          if (bufferEntry.length === 0) return null;
          const index = Math.floor(Math.random() * bufferEntry.length);
          return bufferEntry[Math.max(0, Math.min(index, bufferEntry.length - 1))];
        }
        return bufferEntry;
      };
      const usableBuffer = pickBuffer();
      if (!usableBuffer) {
        return;
      }

      const listenerX =
        options.listenerPosition?.x ?? playerPositionRef.current?.x ?? worldX;
      const listenerY =
        options.listenerPosition?.y ?? playerPositionRef.current?.y ?? worldY;

      const dx = worldX - listenerX;
      const dy = worldY - listenerY;
      const chebyshevDistance = Math.max(Math.abs(dx), Math.abs(dy));
      const distanceGain = usePanning
        ? calculateFootstepGain(chebyshevDistance)
        : 1;

      const profileGain = profileDefinition.gain ?? 1;
      const finalGain = Math.max(
        0,
        distanceGain * volume * (usePanning ? 1 : 0.6) * profileGain
      );
      if (finalGain <= 0.001) {
        return;
      }

      const source = audioCtx.createBufferSource();
      source.buffer = usableBuffer;
      const hasSample =
        Array.isArray(profileDefinition.sampleData) &&
        profileDefinition.sampleData.length > 0;
      const playbackBase = hasSample
        ? profileDefinition.samplePlaybackRate ?? 1
        : 0.96;
      const playbackVariance = hasSample
        ? profileDefinition.samplePlaybackVariance ?? 0
        : 0.08;
      const playbackOffset = hasSample
        ? (Math.random() - 0.5) * playbackVariance
        : Math.random() * playbackVariance;
      source.playbackRate.value = Math.max(0.2, playbackBase + playbackOffset);

      const gainNode = audioCtx.createGain();
      gainNode.gain.value = finalGain;

      let panNode = null;
      if (usePanning && typeof audioCtx.createStereoPanner === "function") {
        panNode = audioCtx.createStereoPanner();
        panNode.pan.value = calculateFootstepPan(dx, dy);
      }

      if (panNode) {
        source.connect(gainNode);
        gainNode.connect(panNode);
        panNode.connect(audioCtx.destination);
      } else {
        source.connect(gainNode);
        gainNode.connect(audioCtx.destination);
      }

      const cleanup = () => {
        try {
          source.disconnect();
          gainNode.disconnect();
          panNode?.disconnect();
        } catch (error) {
          // Swallow cleanup failures to avoid noisy logs
        }
      };

      source.onended = cleanup;
      source.start();
    },
    [ensureAudioContext]
  );

  const playBellSound = useCallback(() => {
    const audioCtx = ensureAudioContext();
    if (!audioCtx) return;

    if (!bellBufferRef.current) {
      bellBufferRef.current = createSampleBuffer(
        audioCtx,
        BELL_SAMPLE,
        BELL_SAMPLE_RATE,
        connectSoundGain
      );
    }
    const buffer = bellBufferRef.current;
    if (!buffer) return;

    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    const gainNode = audioCtx.createGain();
    gainNode.gain.value = 0.8;
    source.connect(gainNode);
    gainNode.connect(audioCtx.destination);

    const cleanup = () => {
      try {
        source.disconnect();
        gainNode.disconnect();
      } catch (error) {
        // ignore
      }
    };

    source.onended = cleanup;
    source.start();
  }, [ensureAudioContext]);

  const getPointerType = useCallback((event) => {
    if (!event || !event.data) return "mouse";
    return (
      event.data.pointerType || event.data.originalEvent?.pointerType || "mouse"
    );
  }, []);

  const { user } = useAuthStore();
  const playerHeadColor = useMemo(
    () => uniqueColorFromString(user?.user_id || user?.email || "guest"),
    [user?.user_id, user?.email]
  );

  const [viewport, setViewport] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });

  const getLandTint = useCallback((land) => {
    if (!land || !land.fenced) return 0xffffff;
    return land.guest_access ? 0xffc857 : 0xff6666;
  }, []);

  const drawHeadGraphic = useCallback((graphic, color) => {
    if (!graphic) return;
    graphic.clear();
    graphic.beginFill(color);
    graphic.lineStyle(2, 0x000000, 0.15);
    graphic.drawCircle(0, 0, LAND_SIZE * 0.38);
    graphic.endFill();
  }, []);

  const updatePlayerGraphicsPosition = useCallback(() => {
    if (!playerContainerRef.current) return;
    const { x, y } = playerPositionRef.current;
    playerContainerRef.current.position.set(
      x * LAND_SIZE,
      y * LAND_SIZE
    );
  }, []);

  const drawOccupancyIcon = useCallback((indicator, data) => {
    if (!indicator) return;
    const { count, colors } = data;
    const { bubble, label } = indicator;
    bubble.clear();
    label.visible = false;

    const colorAt = (index) =>
      Number.isFinite(colors?.[index]) ? colors[index] : OCCUPANCY_COLOR;

    const drawMiniBubble = (cx, cy, radius, color, tailDirection = 1) => {
      const alpha = 0.95;
      bubble.lineStyle(1, 0xffffff, 0.8);
      bubble.beginFill(color, alpha);
      bubble.drawCircle(cx, cy, radius);
      bubble.endFill();

      const tailSize = Math.max(3, radius * 0.3);
      const tailY = cy + radius - 2;
      bubble.beginFill(color, alpha);
      bubble.moveTo(cx - tailSize, tailY);
      bubble.lineTo(cx, tailY + tailDirection * (tailSize + 4));
      bubble.lineTo(cx + tailSize, tailY);
      bubble.closePath();
      bubble.endFill();
    };

    if (count === 2) {
      drawMiniBubble(-9, -2, 9, colorAt(0));
      drawMiniBubble(9, -1, 9, colorAt(1));
      return;
    }

    if (count === 3) {
      drawMiniBubble(-10, 1, 8, colorAt(0));
      drawMiniBubble(10, 1, 8, colorAt(1));
      drawMiniBubble(0, -12, 6, colorAt(2), -1);
      return;
    }

    const width = 36;
    const height = 24;
    bubble.lineStyle(1, 0xffffff, 0.85);
    bubble.beginFill(OCCUPANCY_COLOR, 0.92);
    bubble.drawRoundedRect(-width / 2, -height / 2, width, height, 10);
    bubble.endFill();

    bubble.beginFill(OCCUPANCY_COLOR, 0.92);
    bubble.moveTo(-6, height / 2 - 2);
    bubble.lineTo(0, height / 2 + 8);
    bubble.lineTo(6, height / 2 - 2);
    bubble.lineTo(-6, height / 2 - 2);
    bubble.endFill();

    label.text = `${count}`;
    label.visible = true;
    label.style = new PIXI.TextStyle({
      fill: 0xffffff,
      fontSize: count > 9 ? 13 : 14,
      fontWeight: "bold",
      fontFamily: "Arial",
    });
  }, []);

  const getOrCreateOccupancyIndicator = useCallback((key) => {
    if (!occupancyLayerRef.current) return null;
    let indicator = occupancyIndicatorsRef.current.get(key);
    if (indicator) return indicator;

    const container = new PIXI.Container();
    container.zIndex = 2;

    const bubble = new PIXI.Graphics();
    bubble.lineStyle(1, 0xffffff, 0.7);
    bubble.beginFill(0x2563eb, 0.92);
    bubble.drawRoundedRect(-18, -18, 36, 26, 12);
    bubble.moveTo(-6, 8);
    bubble.lineTo(0, 16);
    bubble.lineTo(6, 8);
    bubble.lineTo(-6, 8);
    bubble.endFill();

    const label = new PIXI.Text("2", {
      fill: 0xffffff,
      fontSize: 14,
      fontWeight: "bold",
      fontFamily: "Arial",
    });
    label.anchor.set(0.5);
    label.position.set(0, -4);

    container.addChild(bubble, label);
    occupancyLayerRef.current.addChild(container);

    indicator = { container, bubble, label };
    occupancyIndicatorsRef.current.set(key, indicator);
    return indicator;
  }, []);

  const updateOccupancyIndicators = useCallback(
    (counts) => {
      if (!occupancyLayerRef.current) return;
      const visibleKeys = new Set();

      counts.forEach((data, key) => {
        const count = data?.count ?? 0;
        if (count < 2) return;
        const indicator = getOrCreateOccupancyIndicator(key);
        if (!indicator) return;
        const { x, y } = parseTileKey(key);
        indicator.container.position.set(
          (x + 0.5) * LAND_SIZE,
          (y - 0.25) * LAND_SIZE
        );
        drawOccupancyIcon(indicator, data);
        visibleKeys.add(key);
      });

      occupancyIndicatorsRef.current.forEach((indicator, key) => {
        if (visibleKeys.has(key)) return;
        if (indicator.container.parent) {
          indicator.container.parent.removeChild(indicator.container);
        }
        occupancyIndicatorsRef.current.delete(key);
      });
    },
    [getOrCreateOccupancyIndicator]
  );

  const startStep = useCallback((dx, dy) => {
    if (dx === 0 && dy === 0) return;

    const startX = playerPositionRef.current.x;
    const startY = playerPositionRef.current.y;
    const endX = startX + dx;
    const endY = startY + dy;

    playerStepRef.current = {
      active: true,
      startX,
      startY,
      endX,
      endY,
      elapsed: 0,
      duration: TILE_STEP_DURATION,
    };
    const profileKey = getBiomeProfileForCoords(endX, endY);
    playFootstepSound(endX, endY, {
      usePanning: false,
      profileKey,
    });
    if (pendingCenterOnMoveRef.current) {
      autoCenterRef.current = true;
      pendingCenterOnMoveRef.current = false;
    }
  }, [getBiomeProfileForCoords, playFootstepSound]);

  const getInputDirection = useCallback(() => {
    const { x, y } = movementDirectionRef.current;
    const absX = Math.abs(x);
    const absY = Math.abs(y);

    if (absX < INPUT_DEADZONE && absY < INPUT_DEADZONE) {
      return null;
    }

    if (absX >= absY) {
      return { dx: x > 0 ? 1 : -1, dy: 0 };
    }

    return { dx: 0, dy: y > 0 ? 1 : -1 };
  }, []);

  const requestNextStep = useCallback(() => {
    if (!playerInitializedRef.current) return;
    if (playerStepRef.current.active) return;

    const direction = getInputDirection();
    if (!direction) return;

    startStep(direction.dx, direction.dy);
  }, [getInputDirection, startStep]);

  const updateMovementVector = useCallback(() => {
    if (touchDirectionRef.current.active) {
      movementDirectionRef.current = {
        x: touchDirectionRef.current.x,
        y: touchDirectionRef.current.y,
      };
    } else {
      movementDirectionRef.current = {
        x: keyboardDirectionRef.current.x,
        y: keyboardDirectionRef.current.y,
      };
    }
    requestNextStep();
  }, [requestNextStep]);

  const syncPlayerToCamera = useCallback(() => {
    const cam = cameraRef.current;
    if (!cam) return;
    if (!playerContainerRef.current) return;

    const snappedX = Math.floor(cam.x) + 0.5;
    const snappedY = Math.floor(cam.y) + 0.5;
    playerPositionRef.current = { x: snappedX, y: snappedY };
    playerStepRef.current.active = false;
    playerStepRef.current.elapsed = 0;
    playerStepRef.current.startX = snappedX;
    playerStepRef.current.startY = snappedY;
    playerStepRef.current.endX = snappedX;
    playerStepRef.current.endY = snappedY;
    playerInitializedRef.current = true;
    updatePlayerGraphicsPosition();
    setCamera(snappedX, snappedY, cameraRef.current?.zoom ?? cam.zoom);
    lastBroadcastRef.current = {
      x: snappedX,
      y: snappedY,
      time: performance.now(),
    };
    wsService.updateLocation(snappedX, snappedY);
  }, [setCamera, updatePlayerGraphicsPosition]);

  const getRandomOwnedLandFromChunks = useCallback(() => {
    if (!chunks || chunks.size === 0) {
      return null;
    }

    const ownedTiles = [];
    chunks.forEach((chunkData) => {
      chunkData.lands?.forEach((land) => {
        if (land.owner_id) {
          ownedTiles.push({ x: land.x, y: land.y });
        }
      });
    });

    if (ownedTiles.length === 0) {
      return null;
    }

    const index = Math.floor(Math.random() * ownedTiles.length);
    return ownedTiles[index];
  }, [chunks]);

  const updateSelectedLandFromPlayer = useCallback(() => {
    const tileX = Math.floor(playerPositionRef.current.x);
    const tileY = Math.floor(playerPositionRef.current.y);

    if (
      lastSelectedTileRef.current.x === tileX &&
      lastSelectedTileRef.current.y === tileY
    ) {
      return;
    }

    lastSelectedTileRef.current = { x: tileX, y: tileY };

    const existingLand = getLandAt(tileX, tileY);
    if (existingLand) {
      setSelectedLand(existingLand);
      return;
    }

    const chunkX = Math.floor(tileX / CHUNK_SIZE);
    const chunkY = Math.floor(tileY / CHUNK_SIZE);

    loadChunk(chunkX, chunkY).then((chunk) => {
      if (!chunk) return;
      if (
        lastSelectedTileRef.current.x !== tileX ||
        lastSelectedTileRef.current.y !== tileY
      ) {
        return;
      }
      const land =
        chunk.lands?.find((l) => l.x === tileX && l.y === tileY) ?? null;
      if (land) {
        setSelectedLand(land);
      }
    });
  }, [getLandAt, loadChunk, setSelectedLand]);

  const jumpPlayerToTile = useCallback(
    (tileX, tileY, options = {}) => {
      const { centerCamera = true } = options;
      if (!playerInitializedRef.current) return;
      if (
        !Number.isFinite(tileX) ||
        !Number.isFinite(tileY)
      ) {
        return;
      }

      const prevX = playerPositionRef.current.x;
      const prevY = playerPositionRef.current.y;
      const targetX = Math.floor(tileX) + 0.5;
      const targetY = Math.floor(tileY) + 0.5;

      playerStepRef.current = {
        active: false,
        startX: targetX,
        startY: targetY,
        endX: targetX,
        endY: targetY,
        elapsed: 0,
        duration: TILE_STEP_DURATION,
      };
      playerPositionRef.current = { x: targetX, y: targetY };
      updatePlayerGraphicsPosition();
      if (centerCamera) {
        const zoom =
          typeof cameraRef.current?.zoom === "number"
            ? cameraRef.current.zoom
            : undefined;
        setCamera(targetX, targetY, zoom);
        pendingCenterOnMoveRef.current = false;
        autoCenterRef.current = false;
      } else {
        pendingCenterOnMoveRef.current = true;
        autoCenterRef.current = false;
      }
      updateSelectedLandFromPlayer();
      if (
        !nearlyEqual(prevX, targetX, 1e-3) ||
        !nearlyEqual(prevY, targetY, 1e-3)
      ) {
        const profileKey = getBiomeProfileForCoords(targetX, targetY);
        playFootstepSound(targetX, targetY, {
          usePanning: false,
          profileKey,
        });
      }
      lastBroadcastRef.current = {
        x: targetX,
        y: targetY,
        time: performance.now(),
      };
      wsService.updateLocation(targetX, targetY);
    },
    [
      setCamera,
      updatePlayerGraphicsPosition,
      updateSelectedLandFromPlayer,
      getBiomeProfileForCoords,
      playFootstepSound,
    ]
  );


  const removeRemotePlayer = useCallback((playerId) => {
    const entry = remotePlayersRef.current.get(playerId);
    if (entry && worldContainerRef.current) {
      worldContainerRef.current.removeChild(entry.container);
    }
    remotePlayersRef.current.delete(playerId);
  }, []);

  const getOrCreateRemotePlayer = useCallback(
    (playerId, username) => {
      let entry = remotePlayersRef.current.get(playerId);
      if (entry) {
        if (username && entry.username !== username) {
          entry.username = username;
        }
        return entry;
      }

      if (!worldContainerRef.current) {
        return null;
      }

      const container = new PIXI.Container();
      container.zIndex = 9000;

      const legRadiusX = LAND_SIZE * 0.18;
      const legRadiusY = LAND_SIZE * 0.24;
      const legOffsetX = LAND_SIZE * 0.32;
      const legOffsetY = LAND_SIZE * 0.4;

      const legColor = 0x6f8094;
      const leftLeg = new PIXI.Graphics();
      leftLeg.beginFill(legColor);
      leftLeg.drawEllipse(0, 0, legRadiusX, legRadiusY);
      leftLeg.endFill();
      leftLeg.position.set(-legOffsetX, legOffsetY);
      leftLeg.baseY = legOffsetY;
      container.addChild(leftLeg);

      const rightLeg = new PIXI.Graphics();
      rightLeg.beginFill(legColor);
      rightLeg.drawEllipse(0, 0, legRadiusX, legRadiusY);
      rightLeg.endFill();
      rightLeg.position.set(legOffsetX, legOffsetY);
      rightLeg.baseY = legOffsetY;
      container.addChild(rightLeg);

      const head = new PIXI.Graphics();
      const color = uniqueColorFromString(playerId || username || "guest");
      drawHeadGraphic(head, color);
      head.zIndex = 5;
      container.addChild(head);

      worldContainerRef.current.addChild(container);

      entry = {
        container,
        head,
        leftLeg,
        rightLeg,
        username,
        color,
        lastUpdate: Date.now(),
        initialized: false,
        animationPhase: 0,
        lastBiomeKey: "default",
        step: {
          active: false,
          startX: 0,
          startY: 0,
          endX: 0,
          endY: 0,
          elapsed: 0,
          duration: TILE_STEP_DURATION,
        },
      };
      remotePlayersRef.current.set(playerId, entry);
      return entry;
    },
    [drawHeadGraphic]
  );

  const updateRemotePlayer = useCallback(
    (playerId, username, x, y) => {
      if (!playerId || playerId === user?.user_id) {
        return;
      }
       if (!worldContainerRef.current) {
         pendingRemoteUpdatesRef.current.set(playerId, {
           username,
           x,
           y,
           timestamp: Date.now(),
         });
         return;
       }
      const entry = getOrCreateRemotePlayer(playerId, username);
      if (!entry) return;
      entry.username = username || entry.username;
      entry.lastUpdate = Date.now();

      const targetX = snapToTileCenter(x);
      const targetY = snapToTileCenter(y);
      if (targetX === null || targetY === null) {
        return;
      }
      const biomeProfileKey =
        getBiomeProfileForCoords(targetX, targetY) ||
        entry.lastBiomeKey ||
        "default";
      entry.lastBiomeKey = biomeProfileKey;

      const resetToTarget = ({ emitSound = false } = {}) => {
        entry.container.position.set(targetX * LAND_SIZE, targetY * LAND_SIZE);
        entry.step = {
          active: false,
          startX: targetX,
          startY: targetY,
          endX: targetX,
          endY: targetY,
          elapsed: 0,
          duration: TILE_STEP_DURATION,
        };
        entry.animationPhase = 0;
        if (entry.leftLeg && entry.rightLeg) {
          entry.leftLeg.y = entry.leftLeg.baseY;
          entry.rightLeg.y = entry.rightLeg.baseY;
        }
        if (emitSound) {
          playFootstepSound(targetX, targetY, {
            profileKey: biomeProfileKey,
          });
        }
      };

      if (!entry.initialized) {
        resetToTarget();
        entry.initialized = true;
        return;
      }

      const currentX = entry.container.position.x / LAND_SIZE;
      const currentY = entry.container.position.y / LAND_SIZE;

      if (!Number.isFinite(currentX) || !Number.isFinite(currentY)) {
        resetToTarget();
        return;
      }

      const alreadyHeadingToTarget =
        entry.step?.active &&
        nearlyEqual(entry.step.endX, targetX) &&
        nearlyEqual(entry.step.endY, targetY);

      if (alreadyHeadingToTarget) {
        return;
      }
      const deltaX = targetX - currentX;
      const deltaY = targetY - currentY;
      const distance = Math.hypot(deltaX, deltaY);

      if (distance < 1e-3) {
        resetToTarget();
        return;
      }

      const longJumpThreshold = 12;
      if (distance > longJumpThreshold) {
        resetToTarget({ emitSound: true });
        return;
      }

      entry.step = {
        active: true,
        startX: currentX,
        startY: currentY,
        endX: targetX,
        endY: targetY,
        elapsed: 0,
        duration: Math.max(distance * TILE_STEP_DURATION, TILE_STEP_DURATION * 0.5),
      };
      playFootstepSound(targetX, targetY, {
        profileKey: biomeProfileKey,
      });
    },
    [
      getBiomeProfileForCoords,
      getOrCreateRemotePlayer,
      playFootstepSound,
      user?.user_id,
    ]
  );

  const broadcastPlayerLocation = useCallback(() => {
    if (!user) return;
    const now = performance.now();
    if (now - lastBroadcastRef.current.time < 120) {
      return;
    }
    const { x, y } = playerPositionRef.current;
    if (typeof x !== "number" || typeof y !== "number") {
      return;
    }
    lastBroadcastRef.current = { x, y, time: now };
    wsService.updateLocation(x, y);
  }, [user]);

  const recomputeKeyboardVector = useCallback(() => {
    const state = keyboardStateRef.current;
    let dx = (state.right ? 1 : 0) - (state.left ? 1 : 0);
    let dy = (state.down ? 1 : 0) - (state.up ? 1 : 0);

    if (dx !== 0 || dy !== 0) {
      const len = Math.hypot(dx, dy);
      dx /= len;
      dy /= len;
    }

    keyboardDirectionRef.current = { x: dx, y: dy };
    updateMovementVector();
  }, [updateMovementVector]);

  const applyTouchDirection = useCallback(
    (x, y) => {
      let dx = x;
      let dy = y;
      const length = Math.hypot(dx, dy);
      if (length > 1) {
        dx /= length;
        dy /= length;
      }

      touchDirectionRef.current = { x: dx, y: dy, active: true };
      setTouchPadVector({ x: dx, y: dy, active: true });
      updateMovementVector();
    },
    [updateMovementVector]
  );

  const stopTouchMovement = useCallback(() => {
    touchDirectionRef.current = { x: 0, y: 0, active: false };
    setTouchPadVector({ x: 0, y: 0, active: false });
    updateMovementVector();
  }, [updateMovementVector]);

  const computePadVector = useCallback((event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const relativeX =
      (event.clientX - rect.left - rect.width / 2) / (rect.width / 2);
    const relativeY =
      (event.clientY - rect.top - rect.height / 2) / (rect.height / 2);

    return {
      x: Math.max(-1, Math.min(1, relativeX)),
      y: Math.max(-1, Math.min(1, relativeY)),
    };
  }, []);

  const handleTouchPadPointerDown = useCallback(
    (event) => {
      event.preventDefault();
      const idleBefore =
        keyboardDirectionRef.current.x === 0 &&
        keyboardDirectionRef.current.y === 0 &&
        !touchDirectionRef.current.active &&
        !playerStepRef.current.active;

      touchPadPointerIdRef.current = event.pointerId;
      event.currentTarget.setPointerCapture?.(event.pointerId);
      const vector = computePadVector(event);
      applyTouchDirection(vector.x, vector.y);
      if (idleBefore) {
        if (!pendingCenterOnMoveRef.current) {
          syncPlayerToCamera();
        }
      }
    },
    [
      applyTouchDirection,
      computePadVector,
      syncPlayerToCamera,
    ]
  );

  const handleTouchPadPointerMove = useCallback(
    (event) => {
      if (touchPadPointerIdRef.current !== event.pointerId) return;
      event.preventDefault();
      const vector = computePadVector(event);
      applyTouchDirection(vector.x, vector.y);
    },
    [applyTouchDirection, computePadVector]
  );

  const handleTouchPadPointerUp = useCallback(
    (event) => {
      if (touchPadPointerIdRef.current !== event.pointerId) return;
      event.preventDefault();
      event.currentTarget.releasePointerCapture?.(event.pointerId);
      touchPadPointerIdRef.current = null;
      stopTouchMovement();
    },
    [stopTouchMovement]
  );

  useEffect(() => {
    cameraRef.current = camera;
  }, [camera]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const hasTouchPoints =
      "ontouchstart" in window ||
      (typeof navigator !== "undefined" && navigator.maxTouchPoints > 0);
    const coarsePointer =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(pointer:coarse)").matches;
    const agent =
      typeof navigator !== "undefined" ? navigator.userAgent : "";
    const mobileAgent = /Mobi|Android|iPhone|iPad|iPod|Tablet/i.test(agent);

    setIsTouchDevice(Boolean(hasTouchPoints && (coarsePointer || mobileAgent)));
  }, []);

  useEffect(() => {
    playerHeadColorRef.current = playerHeadColor;
    const headGraphic = playerPartsRef.current.head;
    if (headGraphic) {
      drawHeadGraphic(headGraphic, playerHeadColor);
    }
  }, [playerHeadColor, drawHeadGraphic]);

  useEffect(() => {
    const ownerId = user?.user_id || null;
    setPlayerHomeTiles(null);

    if (lastOwnerIdRef.current === ownerId) {
      return;
    }

    lastOwnerIdRef.current = ownerId;
    spawnResolvedRef.current = false;
    lastSelectedTileRef.current = { x: null, y: null };
    playerInitializedRef.current = false;
    playerStepRef.current = {
      active: false,
      startX: 0,
      startY: 0,
      endX: 0,
      endY: 0,
      elapsed: 0,
      duration: TILE_STEP_DURATION,
    };
  }, [user?.user_id]);

  useEffect(() => {
    if (!user?.user_id) {
      return;
    }

    let cancelled = false;

    const fetchOwnedTiles = async () => {
      try {
        const response = await landsAPI.getOwnerCoordinates(user.user_id, 5000);
        if (!cancelled) {
          const lands = response.data?.lands ?? [];
          setPlayerHomeTiles(lands);
        }
      } catch (error) {
        console.error("Failed to load player-owned lands", error);
        if (!cancelled) {
          setPlayerHomeTiles([]);
        }
      }
    };

    fetchOwnedTiles();
    return () => {
      cancelled = true;
    };
  }, [user?.user_id]);

  useEffect(() => {
    let cancelled = false;

    const loadOnlinePlayers = async () => {
      try {
        const response = await wsAPI.getOnlineUsers();
        if (cancelled) return;
        const users = response.data?.users ?? [];
        users.forEach((onlineUser) => {
          if (
            !onlineUser ||
            onlineUser.user_id === user?.user_id ||
            !onlineUser.presence?.location
          ) {
            return;
          }
          const loc = onlineUser.presence.location;
          updateRemotePlayer(
            onlineUser.user_id,
            onlineUser.username,
            loc.x,
            loc.y
          );
        });
      } catch (error) {
        console.error("Failed to load online users", error);
      }
    };

    loadOnlinePlayers();
    return () => {
      cancelled = true;
    };
  }, [isPlayerReady, updateRemotePlayer, user?.user_id]);

  useEffect(() => {
    if (!isPlayerReady || !worldContainerRef.current) return;
    pendingRemoteUpdatesRef.current.forEach((value, playerId) => {
      updateRemotePlayer(playerId, value.username, value.x, value.y);
      pendingRemoteUpdatesRef.current.delete(playerId);
    });
  }, [isPlayerReady, updateRemotePlayer]);

  useEffect(() => {
    const handleLocation = (payload) => {
      if (!payload || payload.type !== "player_location") return;
      updateRemotePlayer(
        payload.user_id,
        payload.username,
        payload.x,
        payload.y
      );
    };

    const handlePresence = (payload) => {
      if (
        !payload ||
        payload.type !== "presence_update" ||
        payload.status !== "offline"
      ) {
        return;
      }
      removeRemotePlayer(payload.user_id);
    };

    const unsubscribeLocation = wsService.on("player_location", handleLocation);
    const unsubscribePresence = wsService.on(
      "presence_update",
      handlePresence
    );

    return () => {
      if (typeof unsubscribeLocation === "function") {
        unsubscribeLocation();
      }
      if (typeof unsubscribePresence === "function") {
        unsubscribePresence();
      }
    };
  }, [updateRemotePlayer, removeRemotePlayer]);

  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      remotePlayersRef.current.forEach((entry, playerId) => {
        if (now - entry.lastUpdate > 15000) {
          removeRemotePlayer(playerId);
        }
      });
    }, 5000);

    return () => clearInterval(interval);
  }, [removeRemotePlayer]);

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
    const keyMap = {
      ArrowUp: "up",
      ArrowDown: "down",
      ArrowLeft: "left",
      ArrowRight: "right",
      w: "up",
      s: "down",
      a: "left",
      d: "right",
    };

    const isTyping = (target) => {
      if (!target) return false;
      const tag = target.tagName;
      return (
        target.isContentEditable ||
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        tag === "SELECT"
      );
    };

    const handleKeyDown = (event) => {
      const key =
        event.key.length === 1 ? event.key.toLowerCase() : event.key;
      const dir = keyMap[key];
      if (!dir || isTyping(event.target)) return;

      event.preventDefault();

      if (!keyboardStateRef.current[dir]) {
        const idle =
          keyboardDirectionRef.current.x === 0 &&
          keyboardDirectionRef.current.y === 0 &&
          !touchDirectionRef.current.active &&
          !playerStepRef.current.active;
        keyboardStateRef.current[dir] = true;
        if (idle && !pendingCenterOnMoveRef.current) {
          syncPlayerToCamera();
        }
        recomputeKeyboardVector();
      }
    };

    const handleKeyUp = (event) => {
      const key =
        event.key.length === 1 ? event.key.toLowerCase() : event.key;
      const dir = keyMap[key];
      if (!dir || isTyping(event.target)) return;

      event.preventDefault();

      if (keyboardStateRef.current[dir]) {
        keyboardStateRef.current[dir] = false;
        recomputeKeyboardVector();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [recomputeKeyboardVector, syncPlayerToCamera]);

  useEffect(() => {
    const handleBlur = () => {
      keyboardStateRef.current.up = false;
      keyboardStateRef.current.down = false;
      keyboardStateRef.current.left = false;
      keyboardStateRef.current.right = false;
      recomputeKeyboardVector();
      stopTouchMovement();
    };

    window.addEventListener("blur", handleBlur);
    return () => window.removeEventListener("blur", handleBlur);
  }, [recomputeKeyboardVector, stopTouchMovement]);
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

  // Update land graphics when chunk data changes (e.g., fence status, ownership)
  useEffect(() => {
    const ownersToRedraw = new Set();

    chunks.forEach((chunkData) => {
      chunkData.lands?.forEach((land) => {
        const key = `${land.x}_${land.y}`;
        const meta = landLookupRef.current.get(key);
        if (meta) {
          // Update the baseTint if fencing or guest access changed
          const newBaseTint = getLandTint(land);
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

          // Check if ownership changed (land got claimed)
          const cachedOwner = ownershipCacheRef.current.get(key);
          if (land.owner_id && land.owner_id !== cachedOwner?.owner_id) {
            // Update ownership cache
            ownershipCacheRef.current.set(key, {
              owner_id: land.owner_id,
              owner_username: land.owner_username || null,
            });
            // Mark this owner for border redraw
            ownersToRedraw.add(land.owner_id);
          }
        }
      });
    });

    // Redraw borders for owners whose lands changed
    ownersToRedraw.forEach(async (ownerId) => {
      try {
        const response = await landsAPI.getOwnerCoordinates(ownerId, 5000);
        const ownerLands = response.data?.lands || [];
        const ownerUsername =
          response.data?.owner_username || ownerLands[0]?.owner_username || null;

        ownerLandCacheRef.current.set(ownerId, {
          lands: ownerLands,
          owner_username: ownerUsername,
          fetchedAt: Date.now(),
        });

        drawOwnershipBorders(ownerId, ownerLands, user?.user_id);
      } catch (error) {
        console.error(`Failed to refresh ownership for ${ownerId}:`, error);
      }
    });
  }, [chunks, drawOwnershipBorders, user, getLandTint]);

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

    const playerContainer = new PIXI.Container();
    playerContainer.zIndex = 10000;
    worldContainer.addChild(playerContainer);
    playerContainerRef.current = playerContainer;

    const occupancyLayer = new PIXI.Container();
    occupancyLayer.zIndex = 12000;
    worldContainer.addChild(occupancyLayer);
    occupancyLayerRef.current = occupancyLayer;

    const legRadiusX = LAND_SIZE * 0.18;
    const legRadiusY = LAND_SIZE * 0.24;
    const legOffsetX = LAND_SIZE * 0.32;
    const legOffsetY = LAND_SIZE * 0.4;

    const leftLeg = new PIXI.Graphics();
    leftLeg.beginFill(0x8eaccd);
    leftLeg.drawEllipse(0, 0, legRadiusX, legRadiusY);
    leftLeg.endFill();
    leftLeg.position.set(-legOffsetX, legOffsetY);
    leftLeg.baseY = legOffsetY;
    playerContainer.addChild(leftLeg);

    const rightLeg = new PIXI.Graphics();
    rightLeg.beginFill(0x8eaccd);
    rightLeg.drawEllipse(0, 0, legRadiusX, legRadiusY);
    rightLeg.endFill();
    rightLeg.position.set(legOffsetX, legOffsetY);
    rightLeg.baseY = legOffsetY;
    playerContainer.addChild(rightLeg);

    const head = new PIXI.Graphics();
    drawHeadGraphic(head, playerHeadColorRef.current);
    head.zIndex = 5;
    playerContainer.addChild(head);

    playerPartsRef.current = { head, leftLeg, rightLeg };
    updatePlayerGraphicsPosition();
    setIsPlayerReady(true);

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
      if (playerContainer && playerContainer.parent) {
        playerContainer.parent.removeChild(playerContainer);
      }
      if (occupancyLayer && occupancyLayer.parent) {
        occupancyLayer.parent.removeChild(occupancyLayer);
      }
      occupancyIndicatorsRef.current.forEach((indicator) => {
        if (indicator.container.parent) {
          indicator.container.parent.removeChild(indicator.container);
        }
      });
      occupancyIndicatorsRef.current.clear();
      occupancyLayerRef.current = null;
      setIsPlayerReady(false);
      app.destroy(true, { children: true });
      appRef.current = null;
    };
  }, [updatePlayerGraphicsPosition, drawHeadGraphic]);

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

  useEffect(() => {
    if (playerInitializedRef.current) return;
    if (!isPlayerReady) return;
    if (!camera || (camera.x === 0 && camera.y === 0)) return;
    syncPlayerToCamera();
  }, [camera, isPlayerReady, syncPlayerToCamera]);

  useEffect(() => {
    if (!isPlayerReady) return;
    if (spawnResolvedRef.current) return;
    if (!playerContainerRef.current) return;
    if (playerHomeTiles === null) return;

    let spawnTile = null;
    if (playerHomeTiles.length > 0) {
      const index = Math.floor(Math.random() * playerHomeTiles.length);
      spawnTile = playerHomeTiles[index];
    } else {
      spawnTile = getRandomOwnedLandFromChunks();
    }

    if (!spawnTile) {
      return;
    }

    spawnResolvedRef.current = true;
    const rawX =
      spawnTile.x ?? spawnTile.coordinates?.x ?? playerPositionRef.current.x;
    const rawY =
      spawnTile.y ?? spawnTile.coordinates?.y ?? playerPositionRef.current.y;
    const spawnX = Math.floor(rawX) + 0.5;
    const spawnY = Math.floor(rawY) + 0.5;

    playerPositionRef.current = { x: spawnX, y: spawnY };
    playerStepRef.current = {
      active: false,
      startX: spawnX,
      startY: spawnY,
      endX: spawnX,
      endY: spawnY,
      elapsed: 0,
      duration: TILE_STEP_DURATION,
    };
    updatePlayerGraphicsPosition();
    setCamera(spawnX, spawnY, cameraRef.current?.zoom ?? camera.zoom);
    playerInitializedRef.current = true;
    updateSelectedLandFromPlayer();
    lastBroadcastRef.current = {
      x: spawnX,
      y: spawnY,
      time: performance.now(),
    };
    wsService.updateLocation(spawnX, spawnY);
  }, [
    isPlayerReady,
    playerHomeTiles,
    getRandomOwnedLandFromChunks,
    updatePlayerGraphicsPosition,
    setCamera,
    camera.zoom,
    updateSelectedLandFromPlayer,
  ]);

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

        // Apply tint for fenced/access states
        const baseTint = getLandTint(land);
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
              jumpPlayerToTile(land.x, land.y, { centerCamera: false });
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
          const isOwner =
            Boolean(user?.user_id) && land.owner_id === user?.user_id;
          const badgeColor = getMessageBadgeColor(messageCounts, { isOwner });

          if (badgeColor) {
            const baseX = land.x * LAND_SIZE;
            const baseY = land.y * LAND_SIZE;

            const badge = new PIXI.Graphics();
            const badgeSize = LAND_SIZE * 0.3;
            const badgeX = badgeSize / 2 + LAND_SIZE - badgeSize - 2;
            const badgeY = badgeSize / 2 + 2;

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
    jumpPlayerToTile,
    user?.user_id,
    getLandTint,
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
      chunks.forEach((chunkData, chunkId) => {
        const land = chunkData.lands.find((l) => l.land_id === landId);
        if (!land) {
          return;
        }

        const isOwner =
          Boolean(user?.user_id) && land.owner_id === user?.user_id;
        const badgeColor = getMessageBadgeColor(messageCounts, { isOwner });
        if (!badgeColor) {
          return;
        }

        const chunkContainer = landGraphicsRef.current.get(chunkId);
        if (!chunkContainer) {
          return;
        }

        const baseX = land.x * LAND_SIZE;
        const baseY = land.y * LAND_SIZE;

        const badge = new PIXI.Graphics();
        const badgeSize = LAND_SIZE * 0.3;
        const badgeX = badgeSize / 2 + LAND_SIZE - badgeSize - 2;
        const badgeY = badgeSize / 2 + 2;

        badge.beginFill(badgeColor);
        badge.drawCircle(0, 0, badgeSize / 2);
        badge.endFill();

        badge.lineStyle(1, 0xffffff, 1);
        badge.drawCircle(0, 0, badgeSize / 2);
        badge.lineStyle(0);

        badge.x = baseX + badgeX;
        badge.y = baseY + badgeY;

        chunkContainer.addChild(badge);
        badgeGraphicsRef.current.set(landId, { badge, chunkId });
      });
    });

    console.log(`✓ Updated ${badgeGraphicsRef.current.size} badges`);
  }, [unreadMessagesByLand, chunks, user?.user_id]);

  useEffect(() => {
    if (!appRef.current || !appRef.current.ticker) return;

    const ticker = appRef.current.ticker;
    const swingAmplitude = LAND_SIZE * LEG_SWING_MULTIPLIER;

    const followCamera = (targetX, targetY, deltaSeconds) => {
      if (!Number.isFinite(targetX) || !Number.isFinite(targetY)) return;
      if (autoCenterRef.current) {
        const cam = cameraRef.current || {
          x: targetX,
          y: targetY,
        };
        const factor = Math.min(deltaSeconds * CAMERA_RECENTER_SPEED, 1);
        const nextX = cam.x + (targetX - cam.x) * factor;
        const nextY = cam.y + (targetY - cam.y) * factor;
        setCamera(nextX, nextY);
        if (Math.hypot(nextX - targetX, nextY - targetY) <= 0.05) {
          autoCenterRef.current = false;
          setCamera(targetX, targetY);
        }
      } else {
        setCamera(targetX, targetY);
      }
    };

    const handleTick = (delta) => {
      const deltaSeconds = delta / 60;
      if (!playerInitializedRef.current || !playerContainerRef.current) return;

      let step = playerStepRef.current;
      if (!step.active) {
        requestNextStep();
        step = playerStepRef.current;
      }

      let moving = step.active;
      if (step.active) {
        step.elapsed += deltaSeconds;
        const progress = Math.min(step.elapsed / step.duration, 1);
        const newX =
          step.startX + (step.endX - step.startX) * progress;
        const newY =
          step.startY + (step.endY - step.startY) * progress;
        playerPositionRef.current = { x: newX, y: newY };
        updatePlayerGraphicsPosition();
        followCamera(newX, newY, deltaSeconds);

        if (progress >= 1) {
          step.active = false;
          playerPositionRef.current = {
            x: step.endX,
            y: step.endY,
          };
          updatePlayerGraphicsPosition();
          followCamera(step.endX, step.endY, deltaSeconds);
          requestNextStep();
          moving = playerStepRef.current.active;
        }
      }

      const animation = playerAnimationRef.current;
      if (moving) {
        animation.phase += deltaSeconds * WALK_FREQUENCY * Math.PI * 2;
      } else if (animation.phase !== 0) {
        animation.phase = 0;
      }

      const { leftLeg, rightLeg } = playerPartsRef.current;
      if (leftLeg && rightLeg) {
        const swing = moving ? Math.sin(animation.phase) * swingAmplitude : 0;
        leftLeg.y = leftLeg.baseY + swing;
        rightLeg.y = rightLeg.baseY - swing;
      }

      if (!moving) {
        if (autoCenterRef.current) {
          const cam = cameraRef.current;
          if (cam) {
            const dx = cam.x - playerPositionRef.current.x;
            const dy = cam.y - playerPositionRef.current.y;
            const dist = Math.hypot(dx, dy);
            if (dist > 0.05) {
              pendingCenterOnMoveRef.current = true;
            }
          }
        }
        autoCenterRef.current = false;
        updateSelectedLandFromPlayer();
      }

      broadcastPlayerLocation();

      remotePlayersRef.current.forEach((entry) => {
        if (!entry.step) return;
        const leg = entry.leftLeg && entry.rightLeg ? entry : null;
        if (entry.step.active) {
          entry.step.elapsed += deltaSeconds;
          const progress = Math.min(
            entry.step.elapsed / entry.step.duration,
            1
          );
          const nextX =
            entry.step.startX +
            (entry.step.endX - entry.step.startX) * progress;
          const nextY =
            entry.step.startY +
            (entry.step.endY - entry.step.startY) * progress;
          entry.container.position.set(nextX * LAND_SIZE, nextY * LAND_SIZE);

          if (progress >= 1) {
            entry.step.active = false;
            entry.container.position.set(
              entry.step.endX * LAND_SIZE,
              entry.step.endY * LAND_SIZE
            );
            entry.animationPhase = 0;
            if (leg) {
              entry.leftLeg.y = entry.leftLeg.baseY;
              entry.rightLeg.y = entry.rightLeg.baseY;
            }
          } else {
            entry.animationPhase +=
              deltaSeconds * WALK_FREQUENCY * Math.PI * 2;
            if (leg) {
              const swing =
                Math.sin(entry.animationPhase) * swingAmplitude;
              entry.leftLeg.y = entry.leftLeg.baseY + swing;
              entry.rightLeg.y = entry.rightLeg.baseY - swing;
            }
          }
        } else if (leg) {
          if (entry.leftLeg.y !== entry.leftLeg.baseY) {
            entry.leftLeg.y = entry.leftLeg.baseY;
          }
          if (entry.rightLeg.y !== entry.rightLeg.baseY) {
            entry.rightLeg.y = entry.rightLeg.baseY;
          }
        }
      });

      const occupancyData = new Map();
      const trackOccupant = (worldX, worldY, color, isPlayer = false) => {
        if (typeof worldX !== "number" || typeof worldY !== "number") return;
        const key = tileKey(worldX, worldY);
        const entry =
          occupancyData.get(key) || {
            count: 0,
            colors: [],
            containsPlayer: false,
          };
        entry.count += 1;
        if (
          Number.isFinite(color) &&
          entry.colors.length < 3 &&
          !entry.colors.includes(color)
        ) {
          entry.colors.push(color);
        }
        if (isPlayer) {
          entry.containsPlayer = true;
        }
        occupancyData.set(key, entry);
      };

      trackOccupant(
        playerPositionRef.current?.x,
        playerPositionRef.current?.y,
        playerHeadColorRef.current,
        true
      );
      remotePlayersRef.current.forEach((entry) => {
        const px = entry.container?.position?.x ?? null;
        const py = entry.container?.position?.y ?? null;
        if (px === null || py === null) return;
        trackOccupant(px / LAND_SIZE, py / LAND_SIZE, entry.color);
      });

      updateOccupancyIndicators(occupancyData);

      let tileOccupancy = 1;
      occupancyData.forEach((entry) => {
        if (entry.containsPlayer) {
          tileOccupancy = entry.count;
        }
      });
      const previousOccupancy = lastTileOccupancyRef.current;
      if (tileOccupancy >= 2 && previousOccupancy < 2) {
        playBellSound();
      }
      lastTileOccupancyRef.current = tileOccupancy;
    };

    ticker.add(handleTick);
    return () => {
      if (!ticker) return;
      try {
        ticker.remove(handleTick);
      } catch (error) {
        console.warn("Failed to remove ticker callback", error);
      }
    };
  }, [
    requestNextStep,
    setCamera,
    updatePlayerGraphicsPosition,
    updateSelectedLandFromPlayer,
    broadcastPlayerLocation,
    updateOccupancyIndicators,
    playBellSound,
  ]);

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

  const padThumbStyle = {
    left: "50%",
    top: "50%",
    width: "2.5rem",
    height: "2.5rem",
    marginLeft: "-1.25rem",
    marginTop: "-1.25rem",
    transform: `translate(${touchPadVector.x * 36}px, ${
      touchPadVector.y * 36
    }px)`,
    opacity: touchPadVector.active ? 1 : 0.6,
  };

  return (
    <div className="absolute inset-0">
      <div
        ref={canvasRef}
        className="absolute inset-0"
        style={{ cursor: isDraggingRef.current ? "grabbing" : "grab" }}
      />

      <div className="pointer-events-none absolute top-4 left-1/2 -translate-x-1/2 text-xs uppercase tracking-wide text-white/70 hidden md:block">
        Arrow keys to walk the creature
      </div>

      {isTouchDevice && (
        <div className="absolute bottom-6 right-6 z-30 flex flex-col items-center gap-2 pointer-events-none">
          <div
            className="pointer-events-auto w-28 h-28 rounded-full border border-white/30 bg-gray-900/60 backdrop-blur-md relative"
            onPointerDown={handleTouchPadPointerDown}
            onPointerMove={handleTouchPadPointerMove}
            onPointerUp={handleTouchPadPointerUp}
            onPointerCancel={handleTouchPadPointerUp}
          >
            <div
              className="absolute rounded-full bg-blue-400/80 border border-blue-100/80 shadow-lg"
              style={padThumbStyle}
            />
          </div>
          <p className="text-xs text-white/80 font-semibold drop-shadow pointer-events-none">
            Touch & drag to walk
          </p>
        </div>
      )}
    </div>
  );
}

export default WorldRenderer;
