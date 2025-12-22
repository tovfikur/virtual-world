import { useEffect, useRef, useState } from "react";
import { Room, Participant, Track } from "livekit-client";
import toast from "react-hot-toast";
import "./LiveRoom.css";

/**
 * LiveRoom - Livekit-based audio/video streaming for zones
 * Users in same land square can hear/see each other
 * Different land squares = different rooms (isolated)
 */
function LiveRoom({ roomId, land, user }) {
  const [isLive, setIsLive] = useState(false);
  const [mediaType, setMediaType] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [error, setError] = useState(null);
  const roomRef = useRef(null);
  const localVideoRef = useRef(null);
  const remoteVideoRefs = useRef({});

  // Connect to Livekit room
  const startLive = async (type) => {
    if (!roomId || !user) {
      toast.error("Room or user not available");
      return;
    }

    try {
      setError(null);
      const liverKitUrl =
        import.meta.env.VITE_LIVEKIT_URL || "ws://localhost:7880";

      // Get token from backend
      const tokenResponse = await fetch(
        `/api/v1/livekit/token?room=${roomId}&identity=${user.user_id}&username=${user.username}`,
        { credentials: "include" }
      );

      if (!tokenResponse.ok) {
        throw new Error("Failed to get Livekit token");
      }

      const { token } = await tokenResponse.json();

      // Create room
      const room = new Room({
        autoSubscribe: true,
        dynacast: true,
      });

      // Handle participants
      room.on("participantConnected", (participant) => {
        console.log(`[livekit] Participant joined: ${participant.identity}`);
        handleParticipantConnected(participant);
      });

      room.on("participantDisconnected", (participant) => {
        console.log(`[livekit] Participant left: ${participant.identity}`);
        handleParticipantDisconnected(participant);
      });

      // Connect
      console.log(`[livekit] Connecting to room: ${roomId}`);
      await room.connect(liverKitUrl, token, {
        audio: type === "audio" || type === "both",
        video: (type === "video" || type === "both") && {
          width: 640,
          height: 480,
          frameRate: 24,
        },
      });

      console.log(`[livekit] Connected to room ${roomId}`);

      // Display local video if available
      const localParticipant = room.localParticipant;
      if (localParticipant && localVideoRef.current) {
        const videoTrack = localParticipant.getTrack(Track.Source.Camera);
        if (videoTrack?.videoTrack) {
          await videoTrack.videoTrack.attach(localVideoRef.current);
          console.log("[livekit] Local video attached");
        }
      }

      roomRef.current = room;
      setIsLive(true);
      setMediaType(type);
      toast.success(
        `✅ Live ${type === "both" ? "with audio & video" : `with ${type}`}`
      );
    } catch (err) {
      console.error("[livekit] Error starting live:", err);
      setError(err.message);
      toast.error(`❌ Failed to go live: ${err.message}`);
    }
  };

  const stopLive = async () => {
    try {
      if (roomRef.current) {
        console.log("[livekit] Disconnecting from room");
        await roomRef.current.disconnect();
        roomRef.current = null;
      }

      // Clear video references
      Object.values(remoteVideoRefs.current).forEach((div) => {
        if (div) div.innerHTML = "";
      });
      remoteVideoRefs.current = {};

      if (localVideoRef.current) {
        localVideoRef.current.innerHTML = "";
      }

      setIsLive(false);
      setMediaType(null);
      setParticipants([]);
      toast.success("✅ Stopped live");
    } catch (err) {
      console.error("[livekit] Error stopping live:", err);
      toast.error(`Error stopping live: ${err.message}`);
    }
  };

  const handleParticipantConnected = (participant) => {
    setParticipants((prev) => [...prev, participant]);

    // Handle participant updates (subscribe to tracks)
    participant.on("trackSubscribed", (track) => {
      console.log(
        `[livekit] Track subscribed: ${track.kind} from ${participant.identity}`
      );

      if (track.kind === Track.Kind.Video) {
        if (!remoteVideoRefs.current[participant.sid]) {
          remoteVideoRefs.current[participant.sid] =
            document.createElement("div");
          const container = document.getElementById("remote-videos");
          if (container) {
            container.appendChild(remoteVideoRefs.current[participant.sid]);
          }
        }

        const div = remoteVideoRefs.current[participant.sid];
        if (div && track.videoTrack) {
          track.videoTrack.attach(div);
        }
      }

      if (track.kind === Track.Kind.Audio && track.audioTrack) {
        track.audioTrack.attach(document.createElement("audio"));
        console.log(`[livekit] Audio from ${participant.identity} attached`);
      }
    });

    participant.on("trackUnsubscribed", (track) => {
      if (
        track.kind === Track.Kind.Video &&
        remoteVideoRefs.current[participant.sid]
      ) {
        const div = remoteVideoRefs.current[participant.sid];
        if (div) {
          track.videoTrack?.detach(div);
          div.innerHTML = "";
        }
      }
    });
  };

  const handleParticipantDisconnected = (participant) => {
    setParticipants((prev) => prev.filter((p) => p.sid !== participant.sid));

    if (remoteVideoRefs.current[participant.sid]) {
      const div = remoteVideoRefs.current[participant.sid];
      if (div) div.innerHTML = "";
      delete remoteVideoRefs.current[participant.sid];
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (roomRef.current) {
        roomRef.current.disconnect();
      }
    };
  }, []);

  return (
    <div className="live-room">
      <div className="live-controls">
        {!isLive ? (
          <div className="control-buttons">
            <button
              onClick={() => startLive("audio")}
              className="btn btn-audio"
              title="Go live with audio only"
            >
              🎤 Audio
            </button>
            <button
              onClick={() => startLive("video")}
              className="btn btn-video"
              title="Go live with video only"
            >
              📹 Video
            </button>
            <button
              onClick={() => startLive("both")}
              className="btn btn-both"
              title="Go live with audio and video"
            >
              📹🎤 Both
            </button>
          </div>
        ) : (
          <div className="live-status">
            <span className="live-badge">🔴 LIVE ({mediaType})</span>
            <button onClick={stopLive} className="btn btn-stop">
              Stop
            </button>
          </div>
        )}
      </div>

      {error && <div className="error-message">❌ {error}</div>}

      <div className="video-grid">
        {isLive && mediaType !== "audio" && (
          <div className="video-container local">
            <div ref={localVideoRef} className="video-element" />
            <div className="video-label">You</div>
          </div>
        )}

        <div id="remote-videos" className="remote-videos-container" />
      </div>

      <div className="participants-info">
        <p>👥 People in zone: {participants.length + (isLive ? 1 : 0)}</p>
        {participants.length > 0 && (
          <ul>
            {participants.map((p) => (
              <li key={p.sid}>{p.metadata || p.identity}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default LiveRoom;
