import { useCallback, useEffect, useRef, useState } from "react";
import SimplePeer from "simple-peer";
import toast from "react-hot-toast";
import { wsService } from "../services/websocket";

/**
 * LivePanel
 * Lightweight group live-audio/video for the current land room.
 *
 * Flow:
 * - User clicks Go Live (audio-only or audio+video)
 * - We request media, mark as live, and ask the server for current peers
 * - Offers/answers/ICE are relayed via the existing WebSocket connection
 * - Peers connect in a mesh; everyone that is live can see/hear each other
 */
function LivePanel({ roomId, land, user }) {
  const [isLive, setIsLive] = useState(false);
  const [mediaType, setMediaType] = useState(null); // "audio" | "video" | null
  const [localStream, setLocalStream] = useState(null);
  const [peerStreams, setPeerStreams] = useState({});
  const [debugLog, setDebugLog] = useState([]);
  const [inRoom, setInRoom] = useState(false);
  const peersRef = useRef(new Map());

  const log = useCallback((label, payload = {}) => {
    try {
      // eslint-disable-next-line no-console
      console.log(`[live] ${label}`, payload);
      if (typeof window !== "undefined") {
        window.__LIVE_DEBUG = window.__LIVE_DEBUG || [];
        window.__LIVE_DEBUG.push({ ts: Date.now(), label, payload });
      }
      setDebugLog((prev) => [...prev.slice(-40), { ts: Date.now(), label, payload }]);
    } catch (e) {
      /* noop */
    }
  }, []);

  const stopLocalStream = useCallback(() => {
    log("stopLocalStream");
    try {
      localStream?.getTracks().forEach((track) => track.stop());
    } catch (e) {
      // ignore
    }
    setLocalStream(null);
  }, [localStream]);

  const cleanupPeers = useCallback(() => {
    log("cleanupPeers");
    peersRef.current.forEach((peer) => {
      try {
        peer.destroy();
      } catch (e) {
        // ignore
      }
    });
    peersRef.current.clear();
    setPeerStreams({});
  }, []);

  const teardown = useCallback(() => {
    log("teardown");
    cleanupPeers();
    stopLocalStream();
    setIsLive(false);
    setMediaType(null);
  }, [cleanupPeers, stopLocalStream, log]);

  // Stop everything on unmount
  useEffect(() => {
    log("mount", { roomId });
    return () => teardown();
  }, [teardown, log, roomId]);

  useEffect(() => {
    // When room changes, drop current live session
    teardown();
    setInRoom(false);
    if (roomId && inRoom) {
      log("requesting live_status", { roomId });
      wsService.send("live_status", { room_id: roomId });
    }
  }, [roomId, teardown, log, inRoom]);

  const sendSignal = useCallback(
    (targetUserId, type, payload) => {
      log("sendSignal", { targetUserId, type, roomId, payload });
      if (!roomId || !targetUserId) return;
      wsService.send(type, {
        room_id: roomId,
        target_user_id: targetUserId,
        payload,
      });
    },
    [roomId, log]
  );

  const handlePeerSignal = useCallback(
    (peerId, data, initiator) => {
      // simple-peer emits offers/answers/ICE through a single channel
      log("handlePeerSignal", { peerId, initiator, type: data?.type });
      if (!roomId) return;
      if (data.type === "offer") {
        sendSignal(peerId, "live_offer", {
          signal: data,
          media_type: mediaType || "video",
        });
      } else if (data.type === "answer") {
        sendSignal(peerId, "live_answer", { signal: data });
      } else {
        // ICE candidate
        sendSignal(peerId, "live_ice", { signal: data });
      }
    },
    [mediaType, roomId, sendSignal]
  );

  const createPeerConnection = useCallback(
    (peerId, initiator, meta = {}) => {
      log("createPeerConnection", { peerId, initiator, meta, hasStream: !!localStream });
      if (peersRef.current.has(peerId)) {
        return peersRef.current.get(peerId);
      }

      const peer = new SimplePeer({
        initiator,
        trickle: false,
        // Allow view-only if the user isn't broadcasting
        stream: localStream || undefined,
        config: {
          iceServers: [
            { urls: "stun:stun.l.google.com:19302" },
            { urls: "stun:stun1.l.google.com:19302" },
          ],
        },
      });

      peersRef.current.set(peerId, peer);
      setPeerStreams((prev) => ({
        ...prev,
        [peerId]: { ...meta, user_id: peerId },
      }));

      peer.on("signal", (data) => handlePeerSignal(peerId, data, initiator));
      peer.on("stream", (stream) => {
        log("stream received", { from: peerId });
        setPeerStreams((prev) => ({
          ...prev,
          [peerId]: { ...prev[peerId], stream },
        }));
      });
      peer.on("close", () => {
        log("peer close", { peerId });
        peersRef.current.delete(peerId);
        setPeerStreams((prev) => {
          const next = { ...prev };
          delete next[peerId];
          return next;
        });
      });
      peer.on("error", (err) => {
        log("peer error", err);
        peer.destroy();
      });

      return peer;
    },
    [handlePeerSignal, localStream, log]
  );

  const requestMedia = useCallback(async (mode) => {
    log("requestMedia", { mode });
    if (!navigator?.mediaDevices?.getUserMedia) {
      throw new Error("Media devices are not available in this browser.");
    }
    const constraints = {
      audio: true,
      video: mode === "video",
    };
    return navigator.mediaDevices.getUserMedia(constraints);
  }, []);

  const startLive = useCallback(
    async (mode) => {
      log("startLive click", { mode, roomId });
      if (!roomId) {
        toast.error("Join a land first.");
        return;
      }
      try {
        const stream = await requestMedia(mode);
        log("media granted", { tracks: stream?.getTracks()?.map((t) => t.kind) });
        setLocalStream(stream);
        setIsLive(true);
        setMediaType(mode === "video" ? "video" : "audio");
        wsService.send("live_start", {
          room_id: roomId,
          media_type: mode === "video" ? "video" : "audio",
        });
        log("live_start sent", { roomId });
      } catch (error) {
        log("Failed to start live session", { error });
        toast.error(
          error?.message || "Failed to access microphone/camera. Check permissions."
        );
        teardown();
      }
    },
    [requestMedia, roomId, teardown, log]
  );

  const stopLive = useCallback(() => {
    log("stopLive click", { roomId });
    if (roomId) {
      wsService.send("live_stop", { room_id: roomId });
    }
    teardown();
  }, [roomId, teardown, log]);

  const handlePeerList = useCallback(
    (message) => {
      if (message.room_id !== roomId) return;
      log("live_peers received", message);

      // Update known peers for UI
      const indexed = {};
      (message.peers || []).forEach((peer) => {
        indexed[peer.user_id] = peer;
      });
      setPeerStreams((prev) => ({ ...prev, ...indexed }));

      // Initiate offers to all live broadcasters so we can view them (even if we're not broadcasting)
      (message.peers || []).forEach((peer) => {
        if (peer.user_id === user?.user_id) return;
        createPeerConnection(peer.user_id, true, peer);
      });
    },
    [createPeerConnection, roomId, user?.user_id]
  );

  const handleOffer = useCallback(
    (message) => {
      if (message.room_id !== roomId) return;
      log("offer received", message);
      const from = message.from_user_id;
      const signal = message.payload?.signal;
      if (!from || !signal) return;

      let peer = peersRef.current.get(from);
      if (!peer) {
        peer = createPeerConnection(from, false, {
          media_type: message.payload?.media_type || "video",
        });
      }
      peer?.signal(signal);
    },
    [createPeerConnection, roomId]
  );

  const handleAnswerOrIce = useCallback(
    (message) => {
      if (message.room_id !== roomId) return;
      log("answer/ice received", message);
      const from = message.from_user_id;
      const signal = message.payload?.signal;
      if (!from || !signal) return;
      const peer = peersRef.current.get(from);
      peer?.signal(signal);
    },
    [roomId]
  );

  const handlePeerLeft = useCallback((message) => {
    if (message.room_id !== roomId) return;
    log("peer left", message);
    const peerId = message.user_id;
    if (!peerId) return;
    const peer = peersRef.current.get(peerId);
    if (peer) {
      peer.destroy();
      peersRef.current.delete(peerId);
    }
    setPeerStreams((prev) => {
      const next = { ...prev };
      delete next[peerId];
      return next;
    });
  }, [roomId]);

  useEffect(() => {
    const unsubPeers = wsService.on("live_peers", handlePeerList);
    const unsubJoined = wsService.on("live_peer_joined", (msg) => {
      if (msg.room_id !== roomId) return;
      log("live_peer_joined", msg);
      setPeerStreams((prev) => ({
        ...prev,
        [msg.user_id]: {
          user_id: msg.user_id,
          username: msg.username,
          media_type: msg.media_type,
        },
      }));
      if (msg.user_id !== user?.user_id) {
        createPeerConnection(msg.user_id, true, {
          media_type: msg.media_type,
          username: msg.username,
        });
      }
    });
    const unsubLeft = wsService.on("live_peer_left", handlePeerLeft);
    const unsubOffer = wsService.on("live_offer", handleOffer);
    const unsubAnswer = wsService.on("live_answer", handleAnswerOrIce);
    const unsubIce = wsService.on("live_ice", handleAnswerOrIce);

    return () => {
      unsubPeers();
      unsubJoined();
      unsubLeft();
      unsubOffer();
      unsubAnswer();
      unsubIce();
    };
  }, [createPeerConnection, handleAnswerOrIce, handleOffer, handlePeerLeft, handlePeerList, roomId, user?.user_id, log]);

  useEffect(() => {
    const unsubJoinedRoom = wsService.on("joined_room", (msg) => {
      if (msg.room_id === roomId) {
        log("joined_room ack", msg);
        setInRoom(true);
        wsService.send("live_status", { room_id: roomId });
      }
    });
    const unsubLeftRoom = wsService.on("left_room", (msg) => {
      if (msg.room_id === roomId) {
        log("left_room ack", msg);
        setInRoom(false);
      }
    });
    return () => {
      unsubJoinedRoom();
      unsubLeftRoom();
    };
  }, [roomId, log]);

  const liveCount = Object.keys(peerStreams).length + (isLive ? 1 : 0);
  const roomLabel = land ? `(${land.x}, ${land.y})` : roomId;

  const renderMediaTile = (peerId, data, isSelf = false) => {
    const isVideo = data?.media_type !== "audio";
    const label = isSelf ? "You" : data?.username || peerId?.slice(0, 6) || "User";
    const stream = data?.stream;

    return (
      <div
        key={peerId}
        className="bg-gray-900/40 border border-gray-700 rounded-lg p-2 flex flex-col gap-2"
      >
        <div className="flex items-center justify-between text-xs text-gray-300">
          <span className="font-semibold">
            {label} {isSelf ? "(live)" : ""}
          </span>
          <span className="text-[10px] uppercase tracking-wide text-gray-400">
            {isVideo ? "A/V" : "Audio"}
          </span>
        </div>
        {isVideo ? (
          <video
            className="w-full rounded-md border border-gray-800 bg-black aspect-video object-cover"
            muted={isSelf}
            autoPlay
            playsInline
            ref={(node) => {
              if (node && stream && node.srcObject !== stream) {
                node.srcObject = stream;
              }
            }}
          />
        ) : (
          <div className="flex items-center gap-2 text-gray-200 text-sm">
            <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center text-white font-semibold">
              {label?.[0]?.toUpperCase() || "A"}
            </div>
            <div className="flex-1">
              <p className="font-semibold">{label}</p>
              <p className="text-xs text-gray-400">Audio live</p>
            </div>
            <audio
              autoPlay
              ref={(node) => {
                if (node && stream && node.srcObject !== stream) {
                  node.srcObject = stream;
                }
              }}
            />
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="bg-gray-900/30 border border-gray-700 rounded-lg p-3 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase text-gray-400 tracking-wide">
            Live presence {roomLabel ? `on ${roomLabel}` : ""}
          </p>
          <p className="text-sm text-gray-200">
            {liveCount === 0
              ? "No one is live in this square yet."
              : `${liveCount} live now`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => startLive("audio")}
            disabled={!user || isLive}
            className="px-3 py-1.5 text-xs rounded bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50"
            title={user ? "Broadcast audio" : "Sign in to go live"}
          >
            Go Live (Audio)
          </button>
          <button
            type="button"
            onClick={() => startLive("video")}
            disabled={!user || isLive}
            className="px-3 py-1.5 text-xs rounded bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
            title={user ? "Broadcast audio + video" : "Sign in to go live"}
          >
            Go Live (Video)
          </button>
          <button
            type="button"
            onClick={stopLive}
            disabled={!isLive}
            className="px-3 py-1.5 text-xs rounded bg-red-600 hover:bg-red-700 text-white disabled:opacity-50"
            title="Stop broadcasting"
          >
            Stop
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {isLive &&
          renderMediaTile(
            user?.user_id || "self",
            { media_type: mediaType || "video", stream: localStream, username: user?.username || "You" },
            true
          )}
        {Object.entries(peerStreams).map(([peerId, data]) =>
          renderMediaTile(peerId, data, false)
        )}
      </div>
      <div className="bg-gray-950/40 border border-gray-800 rounded p-2 max-h-32 overflow-y-auto text-[11px] text-gray-300">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-gray-200">Live Debug</span>
          <span className="text-gray-500">
            Room: {roomId || 'n/a'} | InRoom: {inRoom ? 'yes' : 'no'} | WS: {wsService.isConnected ? 'on' : 'off'}
          </span>
        </div>
        {debugLog.length === 0 ? (
          <div className="text-gray-500">No events yet.</div>
        ) : (
          debugLog.map((entry, idx) => (
            <div key={idx} className="text-gray-400">
              {new Date(entry.ts).toLocaleTimeString()} - {entry.label} {entry.payload ? JSON.stringify(entry.payload) : ''}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default LivePanel;
