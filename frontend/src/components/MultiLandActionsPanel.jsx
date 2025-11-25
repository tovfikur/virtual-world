/**
 * Multi-Land Actions Panel
 * Bulk actions for multiple selected lands
 */

import { useState } from 'react';
import { landsAPI, marketplaceAPI } from '../services/api';
import useAuthStore from '../stores/authStore';
import useWorldStore from '../stores/worldStore';
import toast from 'react-hot-toast';

function MultiLandActionsPanel() {
  const { user } = useAuthStore();
  const { selectedLands, clearSelectedLands } = useWorldStore();
  const [showListingForm, setShowListingForm] = useState(false);
  const [listingType, setListingType] = useState('fixed_price');
  const [price, setPrice] = useState('');
  const [buyNowPrice, setBuyNowPrice] = useState('');
  const [duration, setDuration] = useState('24');
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });

  if (selectedLands.length === 0) return null;

  // Count owned lands (with land_id)
  const ownedLands = selectedLands.filter(land => land.land_id);
  const unownedCount = selectedLands.length - ownedLands.length;

  const handleBulkFence = async (enable) => {
    if (selectedLands.length === 0) {
      toast.error('No lands selected');
      return;
    }

    setProcessing(true);
    setProgress({ current: 0, total: selectedLands.length });
    let successCount = 0;
    let failCount = 0;
    const errors = [];

    // Process each land
    for (let i = 0; i < selectedLands.length; i++) {
      const land = selectedLands[i];
      setProgress({ current: i + 1, total: selectedLands.length });
      try {
        // If land doesn't have land_id, we need to fetch it first
        let landId = land.land_id;

        if (!landId) {
          // Try to get land details by coordinates
          try {
            const response = await landsAPI.getLandByCoords(land.x, land.y);
            landId = response.data.land_id;

            // Check if current user owns it
            if (response.data.owner_id !== user?.user_id) {
              errors.push(`(${land.x}, ${land.y}) - Not owned by you`);
              failCount++;
              continue;
            }
          } catch (fetchError) {
            errors.push(`(${land.x}, ${land.y}) - Not claimed yet`);
            failCount++;
            continue;
          }
        }

        // Now fence the land
        await landsAPI.manageFence(
          landId,
          enable,
          enable ? '1234' : null
        );
        successCount++;
      } catch (error) {
        console.error(`Failed to fence land at (${land.x}, ${land.y}):`, error);
        const errorMsg = error.response?.data?.detail || error.message;
        errors.push(`(${land.x}, ${land.y}) - ${errorMsg}`);
        failCount++;
      }
    }

    setProcessing(false);
    setProgress({ current: 0, total: 0 });

    if (successCount > 0) {
      toast.success(`${enable ? 'Enabled' : 'Disabled'} fence on ${successCount} land(s)`);
    }
    if (failCount > 0) {
      const errorSummary = errors.slice(0, 3).join('\n');
      const moreErrors = errors.length > 3 ? `\n...and ${errors.length - 3} more` : '';
      toast.error(`Failed to fence ${failCount} land(s):\n${errorSummary}${moreErrors}`, { duration: 6000 });
      console.error('Fence errors:', errors);
    }

    clearSelectedLands();
  };

  const handleBulkListing = async (e) => {
    e.preventDefault();

    if (selectedLands.length === 0) {
      toast.error('No lands selected');
      return;
    }

    setProcessing(true);
    setProgress({ current: 0, total: selectedLands.length });
    let successCount = 0;
    let failCount = 0;
    const errors = [];

    for (let i = 0; i < selectedLands.length; i++) {
      const land = selectedLands[i];
      setProgress({ current: i + 1, total: selectedLands.length });
      try {
        // If land doesn't have land_id, we need to fetch it first
        let landId = land.land_id;

        if (!landId) {
          // Try to get land details by coordinates
          try {
            const response = await landsAPI.getLandByCoords(land.x, land.y);
            landId = response.data.land_id;

            // Check if current user owns it
            if (response.data.owner_id !== user?.user_id) {
              errors.push(`(${land.x}, ${land.y}) - Not owned by you`);
              failCount++;
              continue;
            }
          } catch (fetchError) {
            errors.push(`(${land.x}, ${land.y}) - Not claimed yet`);
            failCount++;
            continue;
          }
        }

        const listingData = {
          land_id: landId,
          listing_type: listingType,
        };

        // Set appropriate price fields based on listing type
        if (listingType === 'fixed_price') {
          listingData.buy_now_price_bdt = parseInt(price);
        } else if (listingType === 'auction') {
          listingData.starting_price_bdt = parseInt(price);
          listingData.duration_hours = parseInt(duration);
        } else if (listingType === 'auction_with_buynow') {
          listingData.starting_price_bdt = parseInt(price);
          listingData.buy_now_price_bdt = parseInt(buyNowPrice);
          listingData.duration_hours = parseInt(duration);
        }

        await marketplaceAPI.createListing(listingData);
        successCount++;
      } catch (error) {
        console.error(`Failed to list land at (${land.x}, ${land.y}):`, error);
        const errorMsg = error.response?.data?.detail || error.message;
        errors.push(`(${land.x}, ${land.y}) - ${errorMsg}`);
        failCount++;
      }
    }

    setProcessing(false);
    setProgress({ current: 0, total: 0 });

    if (successCount > 0) {
      toast.success(`Created ${successCount} listing(s)`);
    }
    if (failCount > 0) {
      const errorSummary = errors.slice(0, 3).join('\n');
      const moreErrors = errors.length > 3 ? `\n...and ${errors.length - 3} more` : '';
      toast.error(`Failed to list ${failCount} land(s):\n${errorSummary}${moreErrors}`, { duration: 6000 });
      console.error('Listing errors:', errors);
    }

    setShowListingForm(false);
    setPrice('');
    setBuyNowPrice('');
    setDuration('24');
    clearSelectedLands();
  };

  return (
    <div className="fixed bottom-16 md:bottom-20 left-2 right-2 md:left-1/2 md:right-auto md:transform md:-translate-x-1/2 md:min-w-96 md:max-w-md z-30 bg-gray-800 rounded-lg shadow-2xl border-2 border-blue-500 p-3 md:p-4">
      <div className="flex items-center justify-between mb-3 md:mb-4">
        <div>
          <h3 className="text-white font-bold text-base md:text-lg">Multi-Select Mode</h3>
          <p className="text-gray-400 text-xs md:text-sm">
            {selectedLands.length} land{selectedLands.length !== 1 ? 's' : ''} selected
            {ownedLands.length < selectedLands.length && (
              <span className="text-yellow-400 ml-2">
                ({ownedLands.length} owned, {unownedCount} unowned)
              </span>
            )}
          </p>
        </div>
        <button
          onClick={clearSelectedLands}
          className="text-gray-400 hover:text-white transition-colors"
          title="Clear selection"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {processing && progress.total > 0 && (
        <div className="mb-4">
          <div className="flex justify-between text-sm text-gray-300 mb-2">
            <span>Processing...</span>
            <span>{progress.current} / {progress.total}</span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${(progress.current / progress.total) * 100}%` }}
            ></div>
          </div>
        </div>
      )}

      {ownedLands.length > 0 && !showListingForm && (
        <div className="space-y-2">
          <div className="flex gap-2">
            <button
              onClick={() => handleBulkFence(true)}
              disabled={processing}
              className="flex-1 bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-600 text-white font-semibold py-2 px-2 md:px-4 rounded-lg transition-colors text-xs md:text-sm"
            >
              {processing ? 'Processing...' : 'Enable Fence'}
            </button>
            <button
              onClick={() => handleBulkFence(false)}
              disabled={processing}
              className="flex-1 bg-yellow-700 hover:bg-yellow-800 disabled:bg-gray-600 text-white font-semibold py-2 px-2 md:px-4 rounded-lg transition-colors text-xs md:text-sm"
            >
              {processing ? 'Processing...' : 'Disable Fence'}
            </button>
          </div>

          <button
            onClick={() => setShowListingForm(true)}
            disabled={processing}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-semibold py-2 px-2 md:px-4 rounded-lg transition-colors text-xs md:text-sm"
          >
            List on Marketplace
          </button>
        </div>
      )}

      {showListingForm && (
        <div className="bg-gray-700 rounded-lg p-4 space-y-3">
          <h4 className="text-white font-semibold mb-2">Bulk Create Listings ({ownedLands.length})</h4>
          <form onSubmit={handleBulkListing} className="space-y-3">
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
                disabled={processing}
                className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white py-2 rounded transition-colors text-sm font-semibold"
              >
                {processing ? 'Creating...' : 'Create All'}
              </button>
              <button
                type="button"
                onClick={() => setShowListingForm(false)}
                disabled={processing}
                className="flex-1 bg-gray-600 hover:bg-gray-500 disabled:bg-gray-700 text-white py-2 rounded transition-colors text-sm"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-gray-700">
        <p className="text-gray-400 text-xs text-center">
          💡 Hold <kbd className="px-2 py-1 bg-gray-700 rounded text-xs">Ctrl</kbd> or <kbd className="px-2 py-1 bg-gray-700 rounded text-xs">Cmd</kbd> and click to select multiple lands
        </p>
      </div>
    </div>
  );
}

export default MultiLandActionsPanel;
