/**
 * World Page
 * Main game view with PixiJS world renderer
 */

import { useEffect, useState, useRef } from 'react';
import useAuthStore from '../stores/authStore';
import useWorldStore from '../stores/worldStore';
import WorldRenderer from '../components/WorldRenderer';
import HUD from '../components/HUD';
import ChatBox from '../components/ChatBox';
import LandInfoPanel from '../components/LandInfoPanel';
import MultiLandActionsPanel from '../components/MultiLandActionsPanel';

function WorldPage() {
  const { user } = useAuthStore();
  const {
    selectedLand,
    loadWorldInfo,
    focusTarget,
    setCamera,
    setSelectedLand,
  } = useWorldStore((state) => ({
    selectedLand: state.selectedLand,
    loadWorldInfo: state.loadWorldInfo,
    focusTarget: state.focusTarget,
    setCamera: state.setCamera,
    setSelectedLand: state.setSelectedLand,
  }));
  const [showChat, setShowChat] = useState(true);
  const [showLandInfo, setShowLandInfo] = useState(false);
  const handledFocusIdRef = useRef(null);

  useEffect(() => {
    // Load world information on mount
    loadWorldInfo();
  }, [loadWorldInfo]);

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
      console.log(`🎯 Focusing on coordinates: (${focusTarget.center.x}, ${focusTarget.center.y}) with zoom ${focusTarget.zoom ?? 1}`);
      setCamera(focusTarget.center.x, focusTarget.center.y, focusTarget.zoom ?? 1);
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
        <div className="absolute bottom-4 left-2 md:left-4 right-2 md:right-auto z-20">
          <ChatBox onClose={() => setShowChat(false)} />
        </div>
      )}

      {/* Chat Toggle Button (when hidden) */}
      {!showChat && (
        <button
          onClick={() => setShowChat(true)}
          className="absolute bottom-4 left-2 md:left-4 z-20 bg-gray-800 hover:bg-gray-700 text-white px-3 md:px-4 py-2 rounded-lg shadow-lg border border-gray-600 transition-colors"
        >
          <svg className="w-5 h-5 md:w-6 md:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>
      )}

      {/* Land Info Panel - Bottom on Mobile, Right Side on Desktop */}
      {showLandInfo && selectedLand && (
        <div className="absolute bottom-0 left-0 right-0 md:bottom-auto md:top-20 md:left-auto md:right-4 z-20">
          <LandInfoPanel land={selectedLand} />
        </div>
      )}

      {/* Multi-Land Actions Panel - Bottom Center */}
      <MultiLandActionsPanel />

      {/* Controls Help - Bottom Right */}
      <div className="hidden md:block absolute bottom-4 right-4 z-10 bg-gray-800/80 backdrop-blur-sm text-white px-4 py-3 rounded-lg shadow-lg border border-gray-600 text-sm">
        <div className="font-semibold mb-2">Controls:</div>
        <div className="space-y-1 text-gray-300">
          <div><kbd className="px-2 py-1 bg-gray-700 rounded">Click</kbd> - Select land</div>
          <div><kbd className="px-2 py-1 bg-gray-700 rounded">Ctrl+Click</kbd> - Multi-select</div>
          <div><kbd className="px-2 py-1 bg-gray-700 rounded">Drag</kbd> - Pan camera</div>
          <div><kbd className="px-2 py-1 bg-gray-700 rounded">Scroll</kbd> - Zoom in/out</div>
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
