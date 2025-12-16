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
  const { selectedLands, clearSelectedLands, updateLandProperty, isMultiPanelExpanded, setMultiPanelExpanded } = useWorldStore();
  const [showListingForm, setShowListingForm] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [listingType, setListingType] = useState('fixed_price');
  const [price, setPrice] = useState('');
  const [buyNowPrice, setBuyNowPrice] = useState('');
  const [duration, setDuration] = useState('24');
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState({ current: 0, total: 0 });

  // Panel is collapsed by default; only render when expanded
  if (!isMultiPanelExpanded) return null;

  // Categorize lands by ownership
  const myLands = selectedLands.filter(land => land.land_id && land.owner_id === user?.user_id);
  const unownedLands = selectedLands.filter(land => !land.land_id);
  const othersLands = selectedLands.filter(land => land.land_id && land.owner_id !== user?.user_id);

  // For backward compatibility
  const ownedLands = myLands;
  const unownedCount = unownedLands.length;

  // Calculate total price for unowned lands
  const totalPrice = unownedLands.reduce((sum, land) => {
    const landPrice = land.price_base_bdt || land.base_price_bdt || land.base_price || 0;
    return sum + landPrice;
  }, 0);

  const handleBulkPurchase = async () => {
    if (unownedLands.length === 0) {
      toast.error('No unowned lands selected');
      return;
    }

    // Check balance
    if (user.balance_bdt < totalPrice) {
      toast.error(`Insufficient balance. Need ${totalPrice} BDT, have ${user.balance_bdt} BDT`);
      return;
    }

    setShowPaymentModal(false);
    setProcessing(true);
    setProgress({ current: 0, total: unownedLands.length });
    let successCount = 0;
    let failCount = 0;
    const errors = [];

    // Process each unowned land
    for (let i = 0; i < unownedLands.length; i++) {
      const land = unownedLands[i];
      setProgress({ current: i + 1, total: unownedLands.length });

      try {
        // Call admin API to allocate land (purchase)
        const response = await landsAPI.claimLand({
          x: land.x,
          y: land.y,
          biome: land.biome,
          elevation: land.elevation || 0.5,
          price_base_bdt: land.price_base_bdt || land.base_price_bdt || land.base_price
        });

        // Update the chunk data to immediately show ownership
        if (response.data.land_id) {
          updateLandProperty(land.x, land.y, 'land_id', response.data.land_id);
          updateLandProperty(land.x, land.y, 'owner_id', response.data.owner_id);
        }

        successCount++;
      } catch (error) {
        console.error(`Failed to purchase land at (${land.x}, ${land.y}):`, error);
        const errorMsg = error.response?.data?.detail || error.message;
        errors.push(`(${land.x}, ${land.y}) - ${errorMsg}`);
        failCount++;
      }
    }

    setProcessing(false);
    setProgress({ current: 0, total: 0 });

    if (successCount > 0) {
      toast.success(`Successfully purchased ${successCount} land(s)!`);
    }
    if (failCount > 0) {
      const errorSummary = errors.slice(0, 3).join('\n');
      const moreErrors = errors.length > 3 ? `\n...and ${errors.length - 3} more` : '';
      toast.error(`Failed to purchase ${failCount} land(s):\n${errorSummary}${moreErrors}`, { duration: 6000 });
      console.error('Purchase errors:', errors);
    }

    clearSelectedLands();
  };

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

        // Update the chunk data to immediately reflect fence status
        updateLandProperty(land.x, land.y, 'fenced', enable);

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
        <div className="flex items-center gap-2">
          <button
            onClick={clearSelectedLands}
            className="text-gray-400 hover:text-white transition-colors"
            title="Clear selection"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <button
            onClick={() => setMultiPanelExpanded(false)}
            className="text-gray-400 hover:text-white transition-colors"
            title="Collapse panel"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
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

      {/* Purchase Button for Unowned Lands */}
      {unownedLands.length > 0 && !showListingForm && (
        <div className="space-y-2">
          <div className="bg-gray-700 rounded-lg p-3 mb-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-300 text-sm">Total Price:</span>
              <span className="text-green-400 font-bold text-lg">{totalPrice.toLocaleString()} BDT</span>
            </div>
            <p className="text-gray-400 text-xs mt-1">
              {unownedLands.length} unclaimed land{unownedLands.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button
            onClick={() => setShowPaymentModal(true)}
            disabled={processing}
            className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white font-semibold py-3 rounded-lg transition-colors text-sm md:text-base shadow-lg"
          >
            {processing ? 'Processing...' : `Purchase via Marketplace - ${totalPrice.toLocaleString()} BDT`}
          </button>
        </div>
      )}

      {/* Fence & Listing Buttons for Owned Lands */}
      {ownedLands.length > 0 && !showListingForm && (
        <div className={`space-y-2 ${unownedLands.length > 0 ? 'mt-3 pt-3 border-t border-gray-600' : ''}`}>
          <p className="text-gray-400 text-xs mb-2">
            {ownedLands.length} owned land{ownedLands.length !== 1 ? 's' : ''}
          </p>
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

      {/* Payment Modal */}
      {showPaymentModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 rounded-xl shadow-2xl border-2 border-blue-500 max-w-md w-full p-6">
            <div className="flex justify-between items-start mb-6">
              <h3 className="text-xl font-bold text-white">Purchase Lands</h3>
              <button
                onClick={() => setShowPaymentModal(false)}
                className="text-gray-400 hover:text-white transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-4">
              {/* Purchase Summary */}
              <div className="bg-gray-700 rounded-lg p-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-300">Lands:</span>
                  <span className="text-white font-semibold">{unownedLands.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-300">Total Price:</span>
                  <span className="text-green-400 font-bold text-xl">{totalPrice.toLocaleString()} BDT</span>
                </div>
                <div className="border-t border-gray-600 pt-2 mt-2">
                  <div className="flex justify-between">
                    <span className="text-gray-300">Your Balance:</span>
                    <span className="text-yellow-400 font-semibold">{(user?.balance_bdt || 0).toLocaleString()} BDT</span>
                  </div>
                  <div className="flex justify-between mt-1">
                    <span className="text-gray-300">After Purchase:</span>
                    <span className={`font-semibold ${(user?.balance_bdt || 0) >= totalPrice ? 'text-green-400' : 'text-red-400'}`}>
                      {((user?.balance_bdt || 0) - totalPrice).toLocaleString()} BDT
                    </span>
                  </div>
                </div>
              </div>

              {/* Payment Info */}
              <div className="bg-blue-900/30 border border-blue-500/50 rounded-lg p-4">
                <div className="flex items-start space-x-2">
                  <svg className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div className="text-xs text-blue-200">
                    <p className="font-semibold mb-1">Dummy Payment Gateway</p>
                    <p>This is a simulated payment. Funds will be deducted from your account balance immediately.</p>
                  </div>
                </div>
              </div>

              {/* Warning if insufficient balance */}
              {(user?.balance_bdt || 0) < totalPrice && (
                <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-4">
                  <div className="flex items-start space-x-2">
                    <svg className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <p className="text-xs text-red-200">
                      Insufficient balance. You need {(totalPrice - (user?.balance_bdt || 0)).toLocaleString()} more BDT.
                    </p>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setShowPaymentModal(false)}
                  className="flex-1 bg-gray-700 hover:bg-gray-600 text-white font-semibold py-3 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleBulkPurchase}
                  disabled={(user?.balance_bdt || 0) < totalPrice}
                  className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-lg transition-colors shadow-lg"
                >
                  Confirm Purchase
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MultiLandActionsPanel;
