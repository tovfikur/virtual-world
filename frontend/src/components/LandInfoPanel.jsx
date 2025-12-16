/**
 * Land Info Panel Component
 * Displays detailed information about selected land
 */

import { useState, useEffect } from 'react';
import { landsAPI } from '../services/api';
import { getBiomeColorCSS, getBiomeName, getBiomeRarity } from '../utils/biomeColors';
import useAuthStore from '../stores/authStore';

function LandInfoPanel({ land }) {
  const { user } = useAuthStore();
  const [landDetails, setLandDetails] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (land) {
      loadLandDetails();
    }
  }, [land]);

  const loadLandDetails = async () => {
    setLoading(true);
    try {
      // Try to get land from API (if it's owned)
      const response = await landsAPI.getLandByCoords(land.x, land.y);
      const data = response.data;
      setLandDetails({
        ...data,
        x: data.coordinates?.x ?? land.x,
        y: data.coordinates?.y ?? land.y,
        price_base_bdt: data.price_base_bdt ?? data.base_price_bdt ?? land.base_price_bdt,
      });
    } catch (error) {
      console.error('Failed to load land details from API', error);

      // Fallback: try searching lands by owner (if logged in)
      if (user) {
        try {
          const searchResponse = await landsAPI.searchLands({
            owner_id: user.user_id,
            x: land.x,
            y: land.y,
            radius: 1,
            limit: 1,
            page: 1,
          });

          const claimedLand = searchResponse.data?.data?.[0];

          if (claimedLand) {
            setLandDetails({
              ...claimedLand,
              x: claimedLand.coordinates?.x ?? land.x,
              y: claimedLand.coordinates?.y ?? land.y,
              price_base_bdt: claimedLand.price_base_bdt ?? claimedLand.base_price_bdt,
            });
            return;
          }
        } catch (searchError) {
          console.error('Secondary land search failed', searchError);
        }
      }

      // Land not owned yet, use chunk data
      setLandDetails({
        ...land,
        land_id: null,
        owner_id: null,
        owner_username: null,
        fenced: false,
        passcode: null,
        price_base_bdt: land.base_price_bdt ?? land.price_base_bdt ?? land.base_price,
        coordinates: {
          x: land.x,
          y: land.y,
        },
      });
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="w-56 rounded-lg shadow-xl border border-gray-700 p-3" style={{ backgroundColor: '#4a5568' }}>
        <div className="flex justify-center items-center h-12">
          <div className="w-5 h-5 border-3 border-white border-t-transparent rounded-full animate-spin"></div>
        </div>
      </div>
    );
  }

  const isOwned = Boolean(landDetails.owner_id);
  const isOwner = isOwned && landDetails.owner_id === user?.user_id;
  const biomeColor = getBiomeColorCSS(landDetails.biome);

  return (
    <div className="relative w-56 rounded-lg shadow-2xl overflow-hidden" style={{ backgroundColor: biomeColor }}>
      {/* Fencing Ribbon - Top Left Corner */}
      {isOwned && landDetails.fenced && (
        <div className="absolute top-0 left-0 bg-red-600 text-white text-[10px] font-bold px-2 py-1 shadow-lg z-20" style={{ clipPath: 'polygon(0 0, 100% 0, 80% 100%, 0 100%)' }}>
          🔒 FENCED
        </div>
      )}

      {/* Content with Semi-transparent Overlay */}
      <div className="bg-black/30 backdrop-blur-sm p-3 space-y-2">
        {/* Biome Title */}
        <div className="text-center pt-1">
          <h3 className="text-lg font-bold text-white capitalize drop-shadow-lg">{getBiomeName(landDetails.biome)}</h3>
          <p className="text-[10px] text-white/90 drop-shadow">{getBiomeRarity(landDetails.biome)} Biome</p>
        </div>

        {/* Coordinates Badge */}
        <div className="flex justify-center">
          <span className="inline-flex items-center px-3 py-1 rounded-full bg-white/90 backdrop-blur text-gray-900 font-bold text-xs shadow-lg">
            📍 ({landDetails.x}, {landDetails.y})
          </span>
        </div>

        {/* Info Grid - Compact Rows */}
        <div className="space-y-1.5 text-white">
          {/* Price Row */}
          <div className="flex items-center justify-between bg-white/20 backdrop-blur rounded px-2 py-1.5">
            <span className="text-[10px] font-medium">Price</span>
            <span className="text-sm font-bold text-green-300">
              {landDetails.price_base_bdt || landDetails.base_price} BDT
            </span>
          </div>

          {/* Owner Row */}
          <div className="flex items-center justify-between bg-white/20 backdrop-blur rounded px-2 py-1.5">
            <span className="text-[10px] font-medium">Owner</span>
            <span className="text-xs font-semibold">
              {isOwned ? (
                isOwner ? (
                  <span className="text-blue-300">You</span>
                ) : (
                  landDetails.owner_username || 'Unknown'
                )
              ) : (
                <span className="text-gray-300">Unclaimed</span>
              )}
            </span>
          </div>

          {/* Elevation Row (if available) */}
          {landDetails.elevation !== undefined && (
            <div className="flex items-center justify-between bg-white/20 backdrop-blur rounded px-2 py-1.5">
              <span className="text-[10px] font-medium">Elevation</span>
              <span className="text-xs font-semibold">{landDetails.elevation.toFixed(2)}</span>
            </div>
          )}

          {/* Land ID Row (if claimed) */}
          {landDetails.land_id && (
            <div className="flex items-center justify-between bg-white/20 backdrop-blur rounded px-2 py-1.5">
              <span className="text-[10px] font-medium">Land ID</span>
              <button
                onClick={async () => {
                  await navigator.clipboard.writeText(landDetails.land_id);
                  const toast = (await import('react-hot-toast')).default;
                  toast.success('Land ID copied!', { duration: 2000 });
                }}
                className="text-[10px] font-mono hover:text-blue-300 transition-colors flex items-center gap-1"
                title="Click to copy full ID"
              >
                {landDetails.land_id.substring(0, 8)}...
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default LandInfoPanel;
