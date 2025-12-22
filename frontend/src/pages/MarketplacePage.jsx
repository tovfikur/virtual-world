/**
 * Marketplace Page
 * Browse and trade land listings
 */

import { useState, useEffect } from 'react';
import { marketplaceAPI } from '../services/api';
import toast from 'react-hot-toast';
import useAuthStore from '../stores/authStore';

function MarketplacePage() {
  const { user } = useAuthStore();
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    status: 'active',
    listing_type: '',
    biome: '',
    min_price: '',
    max_price: '',
    sort_by: 'created_at_desc'
  });
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    loadListings();
  }, [filters, page]);

  const loadListings = async () => {
    setLoading(true);
    try {
      const params = { ...filters, page, limit: 20 };
      const response = await marketplaceAPI.getListings(params);
      setListings(response.data.data);
      setTotalPages(response.data.pagination.pages);
    } catch (error) {
      toast.error('Failed to load listings');
    } finally {
      setLoading(false);
    }
  };

  const handleBuyNow = async (listingId) => {
    try {
      await marketplaceAPI.buyNow(listingId, 'balance');
      toast.success('Purchase successful!');
      loadListings();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Purchase failed');
    }
  };

  const getBiomeColor = (biome) => {
    const colors = {
      ocean: 'bg-blue-700',
      beach: 'bg-yellow-200',
      plains: 'bg-green-600',
      forest: 'bg-green-800',
      desert: 'bg-orange-400',
      mountain: 'bg-gray-600',
      snow: 'bg-gray-200'
    };
    return colors[biome] || 'bg-gray-500';
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-4 md:p-6">
        <h1 className="text-2xl md:text-3xl font-bold mb-2">Land Marketplace</h1>
        <p className="text-sm md:text-base text-gray-400">Browse and purchase virtual land</p>
      </div>

      <div className="max-w-7xl mx-auto p-3 md:p-6">
        {/* Filters */}
        <div className="bg-gray-800 rounded-lg p-4 md:p-6 mb-4 md:mb-6 border border-gray-700">
          <h2 className="text-lg md:text-xl font-semibold mb-3 md:mb-4">Filters</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 md:gap-4">
            <select
              value={filters.listing_type}
              onChange={(e) => setFilters({ ...filters, listing_type: e.target.value })}
              className="px-4 py-2 bg-gray-700 rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
            >
              <option value="">All Types</option>
              <option value="auction">Auction</option>
              <option value="fixed_price">Fixed Price</option>
              <option value="auction_with_buynow">Auction + Buy Now</option>
            </select>

            <select
              value={filters.biome}
              onChange={(e) => setFilters({ ...filters, biome: e.target.value })}
              className="px-4 py-2 bg-gray-700 rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
            >
              <option value="">All Biomes</option>
              <option value="ocean">Ocean</option>
              <option value="beach">Beach</option>
              <option value="plains">Plains</option>
              <option value="forest">Forest</option>
              <option value="desert">Desert</option>
              <option value="mountain">Mountain</option>
              <option value="snow">Snow</option>
            </select>

            <input
              type="number"
              placeholder="Min Price (BDT)"
              value={filters.min_price}
              onChange={(e) => setFilters({ ...filters, min_price: e.target.value })}
              className="px-4 py-2 bg-gray-700 rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
            />

            <input
              type="number"
              placeholder="Max Price (BDT)"
              value={filters.max_price}
              onChange={(e) => setFilters({ ...filters, max_price: e.target.value })}
              className="px-4 py-2 bg-gray-700 rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
            />

            <select
              value={filters.sort_by}
              onChange={(e) => setFilters({ ...filters, sort_by: e.target.value })}
              className="px-4 py-2 bg-gray-700 rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
            >
              <option value="created_at_desc">Newest First</option>
              <option value="created_at_asc">Oldest First</option>
              <option value="price_asc">Price: Low to High</option>
              <option value="price_desc">Price: High to Low</option>
              <option value="ending_soon">Ending Soon</option>
            </select>
          </div>
        </div>

        {/* Listings Grid */}
        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : listings.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-400 text-lg">No listings found</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
              {listings.map((listing) => {
                // Handle both parcel (new) and single land (legacy) data
                const landCount = listing.land_count || listing.lands?.length || 1;
                const primaryBiome = listing.biomes?.[0] || listing.land_biome || 'unknown';
                const isParcel = landCount > 1;
                const bbox = listing.bounding_box;

                return (
                  <div
                    key={listing.listing_id}
                    className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden hover:border-blue-500 transition-colors"
                  >
                    {/* Biome Badge with Land Count */}
                    <div className={`h-24 ${getBiomeColor(primaryBiome)} flex flex-col items-center justify-center relative`}>
                      <span className="text-white font-bold text-xl capitalize">
                        {primaryBiome}
                      </span>
                      {isParcel && (
                        <span className="absolute top-2 right-2 bg-black bg-opacity-50 text-white text-xs font-bold px-2 py-1 rounded">
                          {landCount} Lands
                        </span>
                      )}
                      {listing.biomes && listing.biomes.length > 1 && (
                        <span className="text-white text-xs mt-1 opacity-80">
                          +{listing.biomes.length - 1} more biome{listing.biomes.length > 2 ? 's' : ''}
                        </span>
                      )}
                    </div>

                    <div className="p-4">
                      <div className="flex justify-between items-start mb-3">
                        <div>
                          <p className="text-gray-400 text-sm">
                            {isParcel ? 'Parcel Area' : 'Coordinates'}
                          </p>
                          {isParcel && bbox ? (
                            <p className="font-semibold text-sm">
                              ({bbox.min_x}, {bbox.min_y}) to ({bbox.max_x}, {bbox.max_y})
                            </p>
                          ) : (
                            <p className="font-semibold">
                              ({listing.land_x || listing.lands?.[0]?.x}, {listing.land_y || listing.lands?.[0]?.y})
                            </p>
                          )}
                        </div>
                        <span className={`px-2 py-1 text-xs rounded ${
                          listing.listing_type === 'auction' ? 'bg-purple-600' :
                          listing.listing_type === 'fixed_price' ? 'bg-green-600' :
                          'bg-blue-600'
                        }`}>
                          {listing.listing_type.replace('_', ' ')}
                        </span>
                      </div>

                    <div className="mb-3">
                      <p className="text-gray-400 text-sm">Current Price</p>
                      <p className="text-2xl font-bold text-blue-400">
                        {listing.current_price_bdt} <span className="text-sm">BDT</span>
                      </p>
                    </div>

                    {listing.bid_count > 0 && (
                      <p className="text-sm text-gray-400 mb-3">
                        {listing.bid_count} bid{listing.bid_count !== 1 ? 's' : ''}
                      </p>
                    )}

                    {listing.ends_at && (
                      <p className="text-sm text-gray-400 mb-3">
                        Ends: {new Date(listing.ends_at).toLocaleString()}
                      </p>
                    )}

                    <p className="text-sm text-gray-400 mb-3">
                      Seller: {listing.seller_username}
                    </p>

                    {listing.buy_now_price_bdt && (
                      <button
                        onClick={() => handleBuyNow(listing.listing_id)}
                        className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-2 rounded-lg transition-colors"
                      >
                        Buy Now - {listing.buy_now_price_bdt} BDT
                      </button>
                    )}
                  </div>
                </div>
                );
              })}
            </div>

            {/* Pagination */}
            <div className="mt-8 flex justify-center items-center space-x-4">
              <button
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                Previous
              </button>
              <span className="text-gray-400">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default MarketplacePage;
