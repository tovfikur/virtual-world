/**
 * World Page
 * Main game view with PixiJS world renderer
 */

import { useEffect, useState, useRef } from "react";
import useAuthStore from "../stores/authStore";
import useWorldStore from "../stores/worldStore";
import WorldRenderer from "../components/WorldRenderer";
import HUD from "../components/HUD";
import ChatBox from "../components/ChatBox";
import LandInfoPanel from "../components/LandInfoPanel";
import MultiLandActionsPanel from "../components/MultiLandActionsPanel";

function WorldPage() {
  const { user } = useAuthStore();
  const {
    selectedLand,
    loadWorldInfo,
    loadUnreadMessages,
    focusTarget,
    setCamera,
    setSelectedLand,
    selectedLands,
    toggleMultiPanelExpanded,
  } = useWorldStore((state) => ({
    selectedLand: state.selectedLand,
    loadWorldInfo: state.loadWorldInfo,
    loadUnreadMessages: state.loadUnreadMessages,
    focusTarget: state.focusTarget,
    setCamera: state.setCamera,
    setSelectedLand: state.setSelectedLand,
    selectedLands: state.selectedLands,
    toggleMultiPanelExpanded: state.toggleMultiPanelExpanded,
  }));
  const [showChat, setShowChat] = useState(true);
  const [showLandInfo, setShowLandInfo] = useState(false);
  const [isPanelExpanded, setIsPanelExpanded] = useState(false);
  const handledFocusIdRef = useRef(null);
  const selectedCoordsLabel = selectedLand
    ? `(${selectedLand.x ?? selectedLand.coordinates?.x ?? "?"}, ${
        selectedLand.y ?? selectedLand.coordinates?.y ?? "?"
      })`
    : null;

  useEffect(() => {
    // Load world information on mount
    loadWorldInfo();

    // Load unread messages if authenticated
    if (user) {
      loadUnreadMessages();

      // Set up interval to periodically refresh unread counts
      const interval = setInterval(() => {
        loadUnreadMessages();
      }, 30000); // Every 30 seconds

      return () => clearInterval(interval);
    }
  }, [loadWorldInfo, loadUnreadMessages, user]);

  useEffect(() => {
    // Listen for unread messages updates
    const handleUnreadUpdate = () => {
      if (user) {
        loadUnreadMessages();
      }
    };

    window.addEventListener("unreadMessagesUpdated", handleUnreadUpdate);
    return () =>
      window.removeEventListener("unreadMessagesUpdated", handleUnreadUpdate);
  }, [loadUnreadMessages, user]);

  useEffect(() => {
    // Show land info panel when land is selected
    setShowLandInfo(!!selectedLand);
  }, [selectedLand]);

  useEffect(() => {
    if (!focusTarget || focusTarget.id === handledFocusIdRef.current) {
      return;
    }

    handledFocusIdRef.current = focusTarget.id;

    // Set camera first
    if (focusTarget.center) {
      console.log(
        `🎯 Focusing on coordinates: (${focusTarget.center.x}, ${
          focusTarget.center.y
        }) with zoom ${focusTarget.zoom ?? 1}`
      );
      setCamera(
        focusTarget.center.x,
        focusTarget.center.y,
        focusTarget.zoom ?? 1
      );
    }

    // Set selected land
    if (focusTarget.primaryLand) {
      setSelectedLand(focusTarget.primaryLand);
    } else if (focusTarget.coordinates?.length) {
      const first = focusTarget.coordinates[0];
      setSelectedLand({
        coordinates: { x: first.x, y: first.y },
        x: first.x,
        y: first.y,
        land_id: first.land_id,
        biome: first.biome,
        price_base_bdt: first.price_base_bdt,
      });
    }
  }, [focusTarget, setCamera, setSelectedLand]);

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-gray-900">
      {/* PixiJS World Renderer */}
      <WorldRenderer />

      {/* HUD - Top Bar */}
      <HUD />

      {/* Chat Box - Bottom Left */}
      {showChat && (
        <div className="absolute bottom-4 left-2 md:left-4 right-2 md:right-auto md:w-96 z-20">
          <ChatBox onClose={() => setShowChat(false)} land={selectedLand} />
        </div>
      )}

      {/* Chat Toggle Button (when hidden) */}
      {!showChat && (
        <button
          onClick={() => setShowChat(true)}
          className="absolute bottom-4 left-2 md:left-4 z-20 bg-gray-800 hover:bg-gray-700 text-white px-3 md:px-4 py-2 rounded-lg shadow-lg border border-gray-600 transition-colors"
        >
          <svg
            className="w-5 h-5 md:w-6 md:h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
        </button>
      )}

      {/* Land Info Panel - Bottom on Mobile, Left Side on Desktop */}
      {isPanelExpanded && (
        <div className="absolute bottom-0 left-0 right-0 md:bottom-auto md:top-32 md:left-4 md:right-auto z-20">
          <div className="relative inline-block">
            <button
              onClick={() => setIsPanelExpanded(false)}
              className="absolute top-2 right-2 z-30 bg-gray-900/90 hover:bg-gray-800 text-white p-2 rounded-full shadow-lg border border-gray-600 transition-colors"
              title="Collapse details"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>
            {selectedLand ? (
              <LandInfoPanel land={selectedLand} />
            ) : (
              <div className="bg-gray-800 rounded-lg p-4 text-gray-300 w-56 shadow-lg border border-gray-700">
                No land selected
              </div>
            )}
          </div>
        </div>
      )}

      {/* Top controls row keeps position in both states */}
      {isPanelExpanded ? (
        <div className="absolute top-20 left-2 md:left-4 z-20 flex justify-start">
          <button
            onClick={() => toggleMultiPanelExpanded()}
            className="bg-yellow-600 hover:bg-yellow-500 text-white p-2 md:px-4 md:py-2 rounded-lg shadow-md border border-yellow-400 transition-colors flex items-center justify-center gap-2 text-sm"
            title="Toggle Multi-Select Panel"
          >
            <svg className="w-5 h-5 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7h18M3 12h18M3 17h18" />
            </svg>
            <span className="hidden md:inline font-semibold whitespace-nowrap">
              Multi-Select{selectedLands && selectedLands.length > 0 ? ` (${selectedLands.length})` : ""}
            </span>
          </button>
        </div>
      ) : (
        <div className="absolute top-20 left-2 md:left-4 z-20 flex gap-2">
          <button
            onClick={() => setIsPanelExpanded(true)}
            className="bg-blue-600 hover:bg-blue-500 text-white p-2 md:px-4 md:py-2 rounded-lg shadow-lg border border-blue-400 transition-colors flex items-center justify-center gap-2"
            title="Show land details"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            <span className="hidden md:inline font-semibold whitespace-nowrap">
              {selectedCoordsLabel ?? "Details"}
            </span>
          </button>

          <button
            onClick={() => toggleMultiPanelExpanded()}
            className="bg-yellow-600 hover:bg-yellow-500 text-white p-2 md:px-4 md:py-2 rounded-lg shadow-md border border-yellow-400 transition-colors flex items-center justify-center gap-2 text-sm"
            title="Toggle Multi-Select Panel"
          >
            <svg className="w-5 h-5 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7h18M3 12h18M3 17h18" />
            </svg>
            <span className="hidden md:inline font-semibold whitespace-nowrap">
              Multi-Select{selectedLands && selectedLands.length > 0 ? ` (${selectedLands.length})` : ""}
            </span>
          </button>
        </div>
      )}

      {/* Multi-Land Actions Panel - Bottom Center */}
      <MultiLandActionsPanel />

      {/* Controls Help - Bottom Right */}
      <div className="hidden md:block absolute bottom-4 right-4 z-10 bg-gray-800/80 backdrop-blur-sm text-white px-4 py-3 rounded-lg shadow-lg border border-gray-600 text-sm">
        <div className="font-semibold mb-2">Controls:</div>
        <div className="space-y-1 text-gray-300">
          <div>
            <kbd className="px-2 py-1 bg-gray-700 rounded">Click</kbd> - Select
            land
          </div>
          <div>
            <kbd className="px-2 py-1 bg-gray-700 rounded">Ctrl+Click</kbd> -
            Multi-select
          </div>
          <div>
            <kbd className="px-2 py-1 bg-gray-700 rounded">Drag</kbd> - Pan
            camera
          </div>
          <div>
            <kbd className="px-2 py-1 bg-gray-700 rounded">Scroll</kbd> - Zoom
            in/out
          </div>
        </div>
      </div>

      {/* Loading Indicator */}
      {!user && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-30">
          <div className="text-center">
            <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-white text-lg">Loading world...</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default WorldPage;
