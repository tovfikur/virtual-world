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

  if (selectedLands.length === 0) return null;

  // Count owned lands (with land_id)
  const ownedLands = selectedLands.filter(land => land.land_id);
  const unownedCount = selectedLands.length - ownedLands.length;

  const handleBulkFence = async (enable) => {
    if (ownedLands.length === 0) {
      toast.error('No owned lands selected');
      return;
    }

    setProcessing(true);
    let successCount = 0;
    let failCount = 0;

    for (const land of ownedLands) {
      try {
        await landsAPI.manageFence(
          land.land_id,
          enable,
          enable ? '1234' : null
        );
        successCount++;
      } catch (error) {
        console.error(`Failed to fence land ${land.land_id}:`, error);
        failCount++;
      }
    }

    setProcessing(false);
    if (successCount > 0) {
      toast.success(`${enable ? 'Enabled' : 'Disabled'} fence on ${successCount} land(s)`);
    }
    if (failCount > 0) {
      toast.error(`Failed to fence ${failCount} land(s)`);
    }

    clearSelectedLands();
  };

  const handleBulkListing = async (e) => {
    e.preventDefault();

    if (ownedLands.length === 0) {
      toast.error('No owned lands selected');
      return;
    }

    setProcessing(true);
    let successCount = 0;
    let failCount = 0;

    for (const land of ownedLands) {
      try {
        const listingData = {
          land_id: land.land_id,
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
        console.error(`Failed to list land ${land.land_id}:`, error);
        failCount++;
      }
    }

    setProcessing(false);
    if (successCount > 0) {
      toast.success(`Created ${successCount} listing(s)`);
    }
    if (failCount > 0) {
      toast.error(`Failed to list ${failCount} land(s)`);
    }

    setShowListingForm(false);
    setPrice('');
    setBuyNowPrice('');
    setDuration('24');
    clearSelectedLands();
  };

  return (
    <div className="fixed bottom-20 left-1/2 transform -translate-x-1/2 z-30 bg-gray-800 rounded-lg shadow-2xl border-2 border-blue-500 p-4 min-w-96">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-white font-bold text-lg">Multi-Select Mode</h3>
          <p className="text-gray-400 text-sm">
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

      {ownedLands.length > 0 && !showListingForm && (
        <div className="space-y-2">
          <div className="flex gap-2">
            <button
              onClick={() => handleBulkFence(true)}
              disabled={processing}
              className="flex-1 bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-600 text-white font-semibold py-2 px-4 rounded-lg transition-colors text-sm"
            >
              {processing ? 'Processing...' : 'Enable Fence All'}
            </button>
            <button
              onClick={() => handleBulkFence(false)}
              disabled={processing}
              className="flex-1 bg-yellow-700 hover:bg-yellow-800 disabled:bg-gray-600 text-white font-semibold py-2 px-4 rounded-lg transition-colors text-sm"
            >
              {processing ? 'Processing...' : 'Disable Fence All'}
            </button>
          </div>

          <button
            onClick={() => setShowListingForm(true)}
            disabled={processing}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-semibold py-2 px-4 rounded-lg transition-colors text-sm"
          >
            List All on Marketplace
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
