import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { wsService } from "../services/websocket";

/**
 * LivePanel - Using RTCPeerConnection directly (no SimplePeer)
 * This avoids SimplePeer's internal stream handling bugs.
 */
function LivePanel({ roomId, land, user }) {
  const [isLive, setIsLive] = useState(false);
  const [mediaType, setMediaType] = useState(null);
  const [localStream, setLocalStream] = useState(null);
  const [peerStreams, setPeerStreams] = useState({});
  const [debugLog, setDebugLog] = useState([]);
  const [inRoom, setInRoom] = useState(false);
  const peersRef = useRef(new Map());
  const streamRef = useRef(null);

  // Log component mount immediately
  console.log("[live] 🎬 LivePanel component mounted/rendered", {
    roomId,
    land: !!land,
    user: !!user,
  });

  const log = useCallback((label, payload = {}) => {
    try {
      console.log(`[live] ${label}`, payload);
      if (typeof window !== "undefined") {
        window.__LIVE_DEBUG = window.__LIVE_DEBUG || [];
        window.__LIVE_DEBUG.push({ ts: Date.now(), label, payload });
      }
      setDebugLog((prev) => [
        ...prev.slice(-40),
        { ts: Date.now(), label, payload },
      ]);
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
    peersRef.current.forEach((peerData) => {
      try {
        peerData.pc?.close();
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

  useEffect(() => {
    streamRef.current = localStream;
  }, [localStream]);

  useEffect(() => {
    log("📍 mount", { roomId, isLive, mediaType });
    return () => {
      // Don't teardown if we're actively streaming or trying to stream
      if (isLive || mediaType) {
        log("🛡️ [UNMOUNT] isLive/mediaType set, skipping teardown", { roomId, isLive, mediaType });
        return;
      }
      log("💥 [UNMOUNT] Calling teardown", { roomId, isLive, mediaType });
      teardown();
    };
  }, [teardown, log, roomId, isLive, mediaType]);

  useEffect(() => {
    // Don't teardown if we're actively trying to be live
    if (isLive || mediaType) {
      log("🛡️ [EFFECT] isLive or mediaType set, skipping teardown", { roomId, isLive, mediaType });
      return;
    }
    
    log("🔍 [EFFECT] Checking inRoom state", { roomId, inRoom, isLive, mediaType });
    if (!roomId || !inRoom) {
      // Only teardown if we're NOT in a room AND NOT trying to be live
      log("💥 [EFFECT] Calling teardown because inRoom=false", { roomId, inRoom });
      teardown();
      setInRoom(false);
      return;
    }
    // We ARE in a room, request live status
    log("requesting live_status", { roomId });
    wsService.send("live_status", { room_id: roomId });
  }, [roomId, teardown, log, inRoom, isLive, mediaType]);

  const sendSignal = useCallback(
    (targetUserId, type, payload) => {
      log("sendSignal", { targetUserId, type, roomId });
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
      log(`📨 [SIGNAL] handlePeerSignal called`, {
        peerId,
        initiator,
        type: data?.type,
      });
      if (!roomId) {
        log("❌ No roomId, cannot send signal");
        return;
      }
      if (data.type === "offer") {
        log(`📤 [OFFER] Sending offer to peer`, { peerId });
        sendSignal(peerId, "live_offer", {
          signal: data,
          media_type: mediaType || "video",
        });
      } else if (data.type === "answer") {
        log(`📤 [ANSWER] Sending answer to peer`, { peerId });
        sendSignal(peerId, "live_answer", { signal: data });
      } else {
        log(`📤 [ICE] Sending ICE candidate to peer`, { peerId });
        sendSignal(peerId, "live_ice", { signal: data });
      }
    },
    [mediaType, roomId, sendSignal, log]
  );

  const createPeerConnection = useCallback(
    (peerId, initiator, meta = {}) => {
      log("createPeerConnection", {
        peerId,
        initiator,
        meta,
      });

      if (peersRef.current.has(peerId)) {
        return peersRef.current.get(peerId).pc;
      }

      const pc = new RTCPeerConnection({
        iceServers: [
          { urls: "stun:stun.l.google.com:19302" },
          { urls: "stun:stun1.l.google.com:19302" },
        ],
      });

      // Handle ICE candidates
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          handlePeerSignal(peerId, event.candidate, initiator);
        }
      };

      // Handle remote stream
      pc.ontrack = (event) => {
        log("🎵 ontrack event fired", {
          peerId,
          kind: event.track.kind,
          enabled: event.track.enabled,
          streamCount: event.streams?.length || 0,
        });
        if (event.streams && event.streams[0]) {
          const remoteStream = event.streams[0];
          log("✅ setting remote stream", {
            peerId,
            trackCount: remoteStream.getTracks().length,
          });
          setPeerStreams((prev) => ({
            ...prev,
            [peerId]: { ...prev[peerId], stream: remoteStream },
          }));
        } else {
          log("⚠️ no streams in ontrack event", { peerId });
        }
      };

      // Handle connection state changes
      pc.onconnectionstatechange = () => {
        log("connectionstatechange", {
          peerId,
          state: pc.connectionState,
        });
        if (
          pc.connectionState === "failed" ||
          pc.connectionState === "closed"
        ) {
          pc.close();
          peersRef.current.delete(peerId);
          setPeerStreams((prev) => {
            const next = { ...prev };
            delete next[peerId];
            return next;
          });
        }
      };

      pc.onerror = (error) => {
        log("pc error", { peerId, error: error.message });
      };

      // Add local stream tracks BEFORE creating offer
      // This ensures the offer includes media sections
      if (streamRef.current && streamRef.current.getTracks().length > 0) {
        const tracks = streamRef.current.getTracks();
        log("🎤 Adding local tracks to peer connection", {
          peerId,
          trackCount: tracks.length,
          kinds: tracks.map((t) => t.kind),
        });
        tracks.forEach((track) => {
          try {
            pc.addTrack(track, streamRef.current);
            log("✅ Track added", {
              peerId,
              kind: track.kind,
              enabled: track.enabled,
            });
          } catch (error) {
            log("❌ Error adding track", { peerId, error: error.message });
          }
        });
      } else {
        log("⚠️ No stream available to add tracks", { peerId });
      }

      // Create offer if initiator
      if (initiator) {
        setTimeout(() => {
          // Small delay to ensure tracks are added
          pc.createOffer()
            .then((offer) => {
              log("📋 Offer created", { peerId });
              return pc.setLocalDescription(offer);
            })
            .then(() => {
              log("📤 Offer set and sending", { peerId });
              handlePeerSignal(peerId, pc.localDescription, initiator);
            })
            .catch((error) => {
              log("❌ Error creating offer", { peerId, error: error.message });
            });
        }, 50);
      }

      const peerData = { pc, initiator, meta };
      peersRef.current.set(peerId, peerData);
      setPeerStreams((prev) => ({
        ...prev,
        [peerId]: { ...meta, user_id: peerId },
      }));

      return pc;
    },
    [handlePeerSignal, log]
  );

  const requestMedia = useCallback(
    async (mode) => {
      log("requestMedia", { mode });
      if (!navigator?.mediaDevices?.getUserMedia) {
        throw new Error("Media devices are not available in this browser.");
      }
      const constraints = {
        audio: true,
        video: mode === "video",
      };
      return navigator.mediaDevices.getUserMedia(constraints);
    },
    [log]
  );

  const startLive = useCallback(
    async (mode) => {
      log("🔴 [START] Go Live button clicked", { mode, roomId, inRoom });
      if (!roomId) {
        log("❌ No roomId, cannot go live");
        toast.error("Join a land first.");
        return;
      }
      try {
        log("📱 Calling getUserMedia with constraints", {
          mode,
          audio: true,
          video: mode === "video",
        });
        const stream = await requestMedia(mode);
        log("✅ [MEDIA] getUserMedia succeeded", {
          tracks: stream
            ?.getTracks()
            ?.map((t) => ({ kind: t.kind, enabled: t.enabled, id: t.id })),
          streamId: stream?.id,
        });

        cleanupPeers();
        setLocalStream(stream);
        streamRef.current = stream;
        log("✅ [STREAM] Local stream stored in ref and state", {
          streamId: stream?.id,
          trackCount: stream?.getTracks()?.length,
        });

        setIsLive(true);
        log("✅ [STATE] isLive set to true");

        setMediaType(mode === "video" ? "video" : "audio");
        log("✅ [STATE] mediaType set", { mediaType: mode });

        log("📨 [BACKEND] Sending live_start to backend", {
          roomId,
          mediaType: mode,
        });
        wsService.send("live_start", {
          room_id: roomId,
          media_type: mode === "video" ? "video" : "audio",
        });
        log("✅ [BACKEND] live_start sent successfully");
      } catch (error) {
        log("❌ [ERROR] Failed to start live session", {
          error: error.message,
          stack: error.stack,
        });
        toast.error(
          error?.message ||
            "Failed to access microphone/camera. Check permissions."
        );
        teardown();
      }
    },
    [requestMedia, roomId, cleanupPeers, teardown, log]
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

      const indexed = {};
      (message.peers || []).forEach((peer) => {
        indexed[peer.user_id] = peer;
      });
      setPeerStreams((prev) => ({ ...prev, ...indexed }));

      log(`📋 Processing ${(message.peers || []).length} peers from list`, {
        peers: (message.peers || []).map(p => ({
          user_id: p.user_id,
          media_type: p.media_type,
        })),
        currentUserId: user?.user_id,
        isLive,
      });

      // Create peer connections to all live users (whether we're broadcasting or just listening)
      (message.peers || []).forEach((peer) => {
        log(`🔍 Checking peer: ${peer.user_id} vs current user: ${user?.user_id}`, {});
        if (peer.user_id === user?.user_id) {
          log(`  ⏭️ Skipping own user`, {});
          return;
        }
        log(`  🔗 Creating peer connection for ${peer.user_id}`, {
          initiator: !!isLive,  // Only initiate if we're live
          mode: isLive ? "broadcaster" : "listener",
        });
        // Create connection regardless of whether we're live
        // Listeners will just answer offers without sending their own stream
        createPeerConnection(peer.user_id, !!isLive, peer);
      });
    },
    [createPeerConnection, roomId, user?.user_id, log, isLive]
  );

  const handleOffer = useCallback(
    (message) => {
      if (message.room_id !== roomId) {
        log("⚠️ ignoring offer from different room", {
          messageRoom: message.room_id,
          currentRoom: roomId,
        });
        return;
      }
      log(`📥 [OFFER] Received offer from ${message.from_user_id}`, {
        from: message.from_user_id,
      });
      const from = message.from_user_id;
      const signal = message.payload?.signal;
      if (!from || !signal) {
        log("❌ [OFFER] Invalid offer - missing from or signal");
        return;
      }

      let pc = peersRef.current.get(from)?.pc;
      if (!pc) {
        log(`🆕 [PEER] Creating new peer connection for offer from ${from}`, {
          from,
        });
        pc = createPeerConnection(from, false, {
          media_type: message.payload?.media_type || "video",
        });
      } else {
        log(`♻️ [PEER] Reusing existing peer connection for ${from}`, { from });
      }

      if (pc && signal.type === "offer") {
        log(`🔄 [SDP] Setting remote description (offer) from ${from}`, {
          from,
          signalType: signal.type,
        });
        pc.setRemoteDescription(new RTCSessionDescription(signal))
          .then(() => {
            log(`✅ [SDP] Offer set as remote description from ${from}`, {
              from,
            });
            log(`🔨 [ANSWER] Creating answer for ${from}`, { from });
            return pc.createAnswer();
          })
          .then((answer) => {
            log(`✅ [ANSWER] Answer created for ${from}`, {
              from,
              type: answer.type,
            });
            return pc.setLocalDescription(answer);
          })
          .then(() => {
            log(
              `✅ [ANSWER] Answer set as local description, sending to ${from}`,
              { from }
            );
            handlePeerSignal(from, pc.localDescription, false);
          })
          .catch((error) => {
            log(
              `❌ [ERROR] Failed to handle offer from ${from}: ${error.message}`,
              { from, error: error.message }
            );
          });
      }
    },
    [createPeerConnection, roomId, log, handlePeerSignal]
  );

  const handleAnswerOrIce = useCallback(
    (message) => {
      if (message.room_id !== roomId) return;
      log("📨 signal received from", {
        from: message.from_user_id,
        type: message.payload?.signal?.type,
      });
      const from = message.from_user_id;
      const signal = message.payload?.signal;
      if (!from || !signal) {
        log("⚠️ invalid signal - missing from or signal");
        return;
      }

      const peerData = peersRef.current.get(from);
      const pc = peerData?.pc;

      if (!pc) {
        log("⚠️ peer not found for signal", { from });
        return;
      }

      if (signal.type === "answer") {
        log("🔄 setting remote description (answer)", { from });
        pc.setRemoteDescription(new RTCSessionDescription(signal))
          .then(() => {
            log("✅ answer set as remote description", { from });
          })
          .catch((error) => {
            log("❌ error setting answer", { from, error: error.message });
          });
      } else if (signal.candidate) {
        log("🧊 adding ICE candidate", { from });
        pc.addIceCandidate(new RTCIceCandidate(signal))
          .then(() => {
            log("✅ ice candidate added", { from });
          })
          .catch((error) => {
            log("❌ error adding ice candidate", {
              from,
              error: error.message,
            });
          });
      }
    },
    [roomId, log]
  );

  const handlePeerLeft = useCallback(
    (message) => {
      if (message.room_id !== roomId) return;
      log("peer left", message);
      const peerId = message.user_id;
      if (!peerId) return;

      const peerData = peersRef.current.get(peerId);
      if (peerData?.pc) {
        peerData.pc.close();
        peersRef.current.delete(peerId);
      }
      setPeerStreams((prev) => {
        const next = { ...prev };
        delete next[peerId];
        return next;
      });
    },
    [roomId, log]
  );

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
  }, [
    createPeerConnection,
    handleAnswerOrIce,
    handleOffer,
    handlePeerLeft,
    handlePeerList,
    roomId,
    user?.user_id,
    log,
  ]);

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
    const label = isSelf
      ? "You"
      : data?.username || peerId?.slice(0, 6) || "User";
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
            {
              media_type: mediaType || "video",
              stream: localStream,
              username: user?.username || "You",
            },
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
            Room: {roomId || "n/a"} | InRoom: {inRoom ? "yes" : "no"} | WS:{" "}
            {wsService.isConnected ? "on" : "off"}
          </span>
        </div>
        {debugLog.length === 0 ? (
          <div className="text-gray-500">No events yet.</div>
        ) : (
          debugLog.map((entry, idx) => (
            <div key={idx} className="text-gray-400">
              {new Date(entry.ts).toLocaleTimeString()} - {entry.label}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default LivePanel;
