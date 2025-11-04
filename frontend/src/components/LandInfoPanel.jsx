/**
 * Land Info Panel Component
 * Displays detailed information about selected land
 */

import { useState, useEffect } from 'react';
import { landsAPI, marketplaceAPI } from '../services/api';
import { getBiomeColorCSS, getBiomeName, getBiomeRarity } from '../utils/biomeColors';
import useAuthStore from '../stores/authStore';
import useWorldStore from '../stores/worldStore';
import toast from 'react-hot-toast';

function LandInfoPanel({ land }) {
  const { user } = useAuthStore();
  const { setSelectedLand } = useWorldStore();
  const [landDetails, setLandDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showListingForm, setShowListingForm] = useState(false);
  const [listingType, setListingType] = useState('fixed_price');
  const [price, setPrice] = useState('');
  const [buyNowPrice, setBuyNowPrice] = useState('');
  const [duration, setDuration] = useState('24');

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

  const handleClose = () => {
    setSelectedLand(null);
  };

  const handleFenceToggle = async () => {
    if (!landDetails.land_id) {
      toast.error('You must own this land to fence it');
      return;
    }

    try {
      await landsAPI.toggleFence(landDetails.land_id, {
        fenced: !landDetails.fenced,
        passcode: landDetails.fenced ? null : '1234', // Default passcode
      });
      toast.success(`Fence ${landDetails.fenced ? 'disabled' : 'enabled'}`);
      loadLandDetails();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to toggle fence');
    }
  };

  const handleCreateListing = async (e) => {
    e.preventDefault();

    if (!landDetails.land_id) {
      toast.error('You must own this land to list it');
      return;
    }

    try {
      const listingData = {
        land_id: landDetails.land_id,
        listing_type: listingType,
        starting_price_bdt: parseInt(price),
        buy_now_price_bdt: listingType === 'auction_with_buynow' ? parseInt(buyNowPrice) : null,
        duration_hours: listingType !== 'fixed_price' ? parseInt(duration) : null,
      };

      await marketplaceAPI.createListing(listingData);
      toast.success('Listing created successfully!');
      setShowListingForm(false);
      loadLandDetails();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create listing');
    }
  };

  if (loading) {
    return (
      <div className="w-80 bg-gray-800 rounded-lg shadow-xl border border-gray-700 p-6">
        <div className="flex justify-center items-center h-32">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
        </div>
      </div>
    );
  }

  const isOwned = Boolean(landDetails.owner_id);
  const isOwner = isOwned && landDetails.owner_id === user?.user_id;
  const biomeColor = getBiomeColorCSS(landDetails.biome);

  return (
    <div className="w-full md:w-96 bg-gray-800 rounded-lg shadow-xl border border-gray-700 overflow-hidden max-h-[90vh] overflow-y-auto">
      {/* Header */}
      <div className="relative h-32 flex items-center justify-center" style={{ backgroundColor: biomeColor }}>
        <div className="text-center text-white">
          <h3 className="text-2xl font-bold capitalize">{getBiomeName(landDetails.biome)}</h3>
          <p className="text-sm opacity-90">{getBiomeRarity(landDetails.biome)} Biome</p>
        </div>
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-white hover:bg-white/20 p-2 rounded-lg transition-colors"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="p-6 space-y-4">
        {/* Coordinates */}
        <div>
          <p className="text-gray-400 text-sm mb-1">Coordinates</p>
          <p className="text-white text-xl font-bold">({landDetails.x}, {landDetails.y})</p>
        </div>

        {/* Price */}
        <div>
          <p className="text-gray-400 text-sm mb-1">Base Price</p>
          <p className="text-green-400 text-2xl font-bold">
            {landDetails.price_base_bdt || landDetails.base_price} BDT
          </p>
        </div>

        {/* Elevation */}
        {landDetails.elevation !== undefined && (
          <div>
            <p className="text-gray-400 text-sm mb-1">Elevation</p>
            <p className="text-white">{landDetails.elevation.toFixed(2)}</p>
          </div>
        )}

        {/* Ownership */}
        <div>
          <p className="text-gray-400 text-sm mb-1">Owner</p>
          <p className="text-white font-semibold">
            {isOwned ? (
              isOwner ? (
                <span className="text-blue-400">You</span>
              ) : (
                landDetails.owner_username || 'Unknown'
              )
            ) : (
              <span className="text-gray-500">Unclaimed</span>
            )}
          </p>
        </div>

        {/* Fencing Status */}
        {isOwned && (
          <div className="flex items-center justify-between py-2 px-3 bg-gray-700 rounded-lg">
            <div className="flex items-center space-x-2">
              <span className="text-yellow-400">🔒</span>
              <span className="text-white text-sm">Fencing</span>
            </div>
            <span className={`text-sm font-semibold ${landDetails.fenced ? 'text-green-400' : 'text-gray-400'}`}>
              {landDetails.fenced ? 'Enabled' : 'Disabled'}
            </span>
          </div>
        )}

        {/* Actions */}
        <div className="space-y-2 pt-4 border-t border-gray-700">
          {!isOwned && (
            <button
              onClick={() => toast('Purchase via Marketplace', { icon: '🏪' })}
              className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-lg transition-colors"
            >
              Buy Land - {landDetails.price_base_bdt || landDetails.base_price} BDT
            </button>
          )}

          {isOwner && (
            <>
              <button
                onClick={handleFenceToggle}
                className="w-full bg-yellow-600 hover:bg-yellow-700 text-white font-semibold py-2 rounded-lg transition-colors"
              >
                {landDetails.fenced ? 'Disable' : 'Enable'} Fence
              </button>

              {!showListingForm ? (
                <button
                  onClick={() => setShowListingForm(true)}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 rounded-lg transition-colors"
                >
                  List on Marketplace
                </button>
              ) : (
                <div className="bg-gray-700 rounded-lg p-4 space-y-3">
                  <h4 className="text-white font-semibold mb-2">Create Listing</h4>
                  <form onSubmit={handleCreateListing} className="space-y-3">
                    <select
                      value={listingType}
                      onChange={(e) => setListingType(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-600 text-white rounded border border-gray-500 focus:border-blue-500 focus:outline-none text-sm"
                    >
                      <option value="fixed_price">Fixed Price</option>
                      <option value="auction">Auction</option>
                      <option value="auction_with_buynow">Auction + Buy Now</option>
                    </select>

                    <input
                      type="number"
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                      placeholder={listingType === 'fixed_price' ? 'Price (BDT)' : 'Starting Price (BDT)'}
                      required
                      className="w-full px-3 py-2 bg-gray-600 text-white rounded border border-gray-500 focus:border-blue-500 focus:outline-none text-sm"
                    />

                    {listingType === 'auction_with_buynow' && (
                      <input
                        type="number"
                        value={buyNowPrice}
                        onChange={(e) => setBuyNowPrice(e.target.value)}
                        placeholder="Buy Now Price (BDT)"
                        required
                        className="w-full px-3 py-2 bg-gray-600 text-white rounded border border-gray-500 focus:border-blue-500 focus:outline-none text-sm"
                      />
                    )}

                    {listingType !== 'fixed_price' && (
                      <select
                        value={duration}
                        onChange={(e) => setDuration(e.target.value)}
                        className="w-full px-3 py-2 bg-gray-600 text-white rounded border border-gray-500 focus:border-blue-500 focus:outline-none text-sm"
                      >
                        <option value="12">12 hours</option>
                        <option value="24">24 hours</option>
                        <option value="48">48 hours</option>
                        <option value="72">72 hours</option>
                        <option value="168">7 days</option>
                      </select>
                    )}

                    <div className="flex space-x-2">
                      <button
                        type="submit"
                        className="flex-1 bg-green-600 hover:bg-green-700 text-white py-2 rounded transition-colors text-sm font-semibold"
                      >
                        Create
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowListingForm(false)}
                        className="flex-1 bg-gray-600 hover:bg-gray-500 text-white py-2 rounded transition-colors text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                </div>
              )}
            </>
          )}
        </div>

        {/* Info */}
        <div className="pt-4 border-t border-gray-700 text-xs text-gray-400">
          <p>Land ID: {landDetails.land_id || 'Not claimed'}</p>
          {landDetails.created_at && (
            <p>Claimed: {new Date(landDetails.created_at).toLocaleDateString()}</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default LandInfoPanel;
