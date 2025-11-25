/**
 * Profile Page
 * User profile with stats and owned lands
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { usersAPI } from '../services/api';
import useAuthStore from '../stores/authStore';
import useWorldStore from '../stores/worldStore';
import toast from 'react-hot-toast';

function ProfilePage() {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const setFocusTarget = useWorldStore((state) => state.setFocusTarget);
  const [stats, setStats] = useState(null);
  const [lands, setLands] = useState([]);
  const [landGroups, setLandGroups] = useState([]);
  const [balance, setBalance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const observerTarget = useRef(null);

  useEffect(() => {
    if (user) {
      loadProfileData();
    } else {
      setLoading(false);
    }
  }, [user]);

  const loadProfileData = async () => {
    try {
      const [statsRes, landsRes, balanceRes] = await Promise.all([
        usersAPI.getUserStats(user.user_id),
        usersAPI.getUserLands(user.user_id, 1, 20),
        usersAPI.getBalance(user.user_id)
      ]);

      setStats(statsRes.data.stats);
      setLands(landsRes.data.data);
      setPagination(landsRes.data.pagination);
      setBalance(balanceRes.data);
    } catch (error) {
      toast.error('Failed to load profile data');
    } finally {
      setLoading(false);
    }
  };

  // Group connected lands together
  const groupConnectedLands = useCallback((landsList) => {
    if (!landsList || landsList.length === 0) return [];

    const groups = [];
    const visited = new Set();

    const findConnected = (land, group) => {
      const key = `${land.coordinates?.x},${land.coordinates?.y}`;
      if (visited.has(key)) return;

      visited.add(key);
      group.push(land);

      // Find adjacent lands (8 directions)
      const x = land.coordinates?.x;
      const y = land.coordinates?.y;
      if (x === undefined || y === undefined) return;

      for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
          if (dx === 0 && dy === 0) continue;

          const adjacent = landsList.find(
            l => l.coordinates?.x === x + dx && l.coordinates?.y === y + dy
          );

          if (adjacent && !visited.has(`${adjacent.coordinates.x},${adjacent.coordinates.y}`)) {
            findConnected(adjacent, group);
          }
        }
      }
    };

    landsList.forEach(land => {
      const key = `${land.coordinates?.x},${land.coordinates?.y}`;
      if (!visited.has(key)) {
        const group = [];
        findConnected(land, group);
        groups.push(group);
      }
    });

    return groups.sort((a, b) => b.length - a.length);
  }, []);

  useEffect(() => {
    if (lands.length > 0) {
      const groups = groupConnectedLands(lands);
      setLandGroups(groups);
    }
  }, [lands, groupConnectedLands]);

  const loadMoreLands = useCallback(async () => {
    if (!pagination?.has_next || loadingMore) return;

    setLoadingMore(true);
    try {
      const nextPage = page + 1;
      const response = await usersAPI.getUserLands(user.user_id, nextPage, 20);

      setLands([...lands, ...response.data.data]);
      setPagination(response.data.pagination);
      setPage(nextPage);
    } catch (error) {
      toast.error('Failed to load more lands');
    } finally {
      setLoadingMore(false);
    }
  }, [pagination, loadingMore, page, user, lands]);

  const handleViewOnMap = useCallback((group) => {
    if (!group || group.length === 0) {
      toast.error('No land data available for this group');
      return;
    }

    const coords = group
      .map((land) => ({
        x: land.coordinates?.x,
        y: land.coordinates?.y,
        land_id: land.land_id,
        biome: land.biome,
        price_base_bdt: land.price_base_bdt,
      }))
      .filter(
        (coord) =>
          coord.x !== undefined &&
          coord.y !== undefined &&
          !Number.isNaN(coord.x) &&
          !Number.isNaN(coord.y)
      );

    if (coords.length === 0) {
      toast.error('This group has no map coordinates yet');
      return;
    }

    const xs = coords.map((c) => c.x);
    const ys = coords.map((c) => c.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);

    const width = Math.max(1, maxX - minX + 1);
    const height = Math.max(1, maxY - minY + 1);
    const maxDimension = Math.max(width, height);

    // Heuristic zoom: keep large estates in view while focusing on smaller plots.
    const targetZoom = Math.min(2, Math.max(0.35, 32 / Math.max(maxDimension, 12)));

    const focusData = {
      id: Date.now(),
      type: 'profile-group',
      ownerId: user?.user_id ?? null,
      ownerUsername: user?.username ?? null,
      coordinates: coords,
      center: {
        x: (minX + maxX) / 2,
        y: (minY + maxY) / 2,
      },
      span: { width, height },
      zoom: targetZoom,
      primaryLand: group[0],
      totalParcels: group.length,
    };

    console.log('🗺️ Setting focus target:', focusData);
    setFocusTarget(focusData);

    toast.success(`Viewing ${group.length} parcels on map`);

    console.log('🧭 Navigating to /world');
    navigate('/world');
  }, [navigate, setFocusTarget, user]);

  // Infinite scroll observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && pagination?.has_next && !loadingMore) {
          loadMoreLands();
        }
      },
      { threshold: 0.1 }
    );

    if (observerTarget.current) {
      observer.observe(observerTarget.current);
    }

    return () => {
      if (observerTarget.current) {
        observer.unobserve(observerTarget.current);
      }
    };
  }, [pagination, loadingMore, loadMoreLands]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-4 md:p-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-2xl md:text-3xl font-bold mb-2">{user.username}</h1>
          <p className="text-sm md:text-base text-gray-400">{user.email}</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-3 md:p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
          {/* Balance Card */}
          <div className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg p-4 md:p-6 shadow-xl">
            <h2 className="text-base md:text-lg font-semibold mb-2 text-blue-100">Balance</h2>
            <p className="text-3xl md:text-4xl font-bold mb-3 md:mb-4">{balance?.balance_bdt || 0} BDT</p>
            <button className="bg-white hover:bg-gray-100 text-blue-900 font-semibold px-3 md:px-4 py-2 rounded-lg transition-colors text-sm md:text-base">
              Top Up
            </button>
          </div>

          {/* Lands Owned */}
          <div className="bg-gray-800 rounded-lg p-4 md:p-6 border border-gray-700">
            <h2 className="text-base md:text-lg font-semibold mb-2 text-gray-300">Lands Owned</h2>
            <p className="text-3xl md:text-4xl font-bold text-green-400">{stats?.lands_owned || 0}</p>
            <p className="text-xs md:text-sm text-gray-400 mt-2">
              Total Value: {stats?.total_land_value_bdt || 0} BDT
            </p>
          </div>

          {/* Transactions */}
          <div className="bg-gray-800 rounded-lg p-4 md:p-6 border border-gray-700">
            <h2 className="text-base md:text-lg font-semibold mb-2 text-gray-300">Transactions</h2>
            <p className="text-3xl md:text-4xl font-bold text-purple-400">{stats?.total_transactions || 0}</p>
            <p className="text-xs md:text-sm text-gray-400 mt-2">
              {stats?.transactions_as_buyer || 0} buys, {stats?.transactions_as_seller || 0} sales
            </p>
          </div>
        </div>

        {/* Owned Lands */}
        <div className="mt-6 md:mt-8">
          <div className="flex justify-between items-center mb-3 md:mb-4">
            <h2 className="text-xl md:text-2xl font-bold">My Lands</h2>
            {pagination && (
              <p className="text-gray-400">
                Showing {lands.length} of {pagination.total} lands
              </p>
            )}
          </div>
          {lands.length === 0 ? (
            <div className="bg-gray-800 rounded-lg p-12 text-center border border-gray-700">
              <p className="text-gray-400 text-lg mb-4">You don't own any land yet</p>
              <a
                href="/marketplace"
                className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
              >
                Browse Marketplace
              </a>
            </div>
          ) : (
            <>
              <div className="space-y-3 md:space-y-4">
                {landGroups.map((group, groupIndex) => (
                  <div
                    key={groupIndex}
                    className="bg-gray-800 rounded-lg p-4 md:p-6 border border-gray-700 hover:border-blue-500 transition-colors"
                  >
                    <div className="flex justify-between items-start mb-3 md:mb-4">
                      <div>
                        <h3 className="text-lg md:text-xl font-bold mb-1">
                          {group.length === 1 ? 'Single Land Parcel' : `Connected Land Group`}
                        </h3>
                        <p className="text-gray-400 text-xs md:text-sm">
                          {group.length} {group.length === 1 ? 'parcel' : 'parcels'} • Total Value: {group.reduce((sum, l) => sum + (l.price_base_bdt || 0), 0)} BDT
                        </p>
                      </div>
                      <span className="px-2 md:px-3 py-1 bg-blue-600 text-xs md:text-sm rounded font-semibold">
                        {group.length}x
                      </span>
                    </div>

                    {/* Coordinates Grid */}
                    <div className="mb-4">
                      <p className="text-gray-400 text-xs mb-2 uppercase">Coordinates:</p>
                      <div className="flex flex-wrap gap-2">
                        {group.slice(0, 20).map((land, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-1 bg-gray-700 text-xs rounded font-mono"
                          >
                            ({land.coordinates?.x ?? '?'}, {land.coordinates?.y ?? '?'})
                          </span>
                        ))}
                        {group.length > 20 && (
                          <span className="px-2 py-1 bg-gray-700 text-xs rounded text-gray-400">
                            +{group.length - 20} more
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Biome Distribution */}
                    <div className="mb-4">
                      <p className="text-gray-400 text-xs mb-2 uppercase">Biomes:</p>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(
                          group.reduce((acc, land) => {
                            const biome = land.biome || 'unknown';
                            acc[biome] = (acc[biome] || 0) + 1;
                            return acc;
                          }, {})
                        ).map(([biome, count]) => (
                          <span
                            key={biome}
                            className="px-2 py-1 bg-green-600 text-xs rounded capitalize"
                          >
                            {biome} ({count})
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Fenced Status */}
                    {group.some(l => l.fenced) && (
                      <div className="mb-4">
                        <span className="px-2 py-1 bg-yellow-600 text-xs rounded">
                          🔒 {group.filter(l => l.fenced).length} Fenced
                        </span>
                      </div>
                    )}

                    <div className="flex flex-col sm:flex-row gap-2">
                      <button
                        onClick={() => handleViewOnMap(group)}
                        className="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-2 rounded-lg transition-colors text-xs md:text-sm font-semibold flex items-center justify-center gap-2"
                      >
                        <svg className="w-3 h-3 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                        </svg>
                        View on Map
                      </button>
                      <button className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg transition-colors text-xs md:text-sm font-semibold">
                        Manage Group
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Infinite Scroll Trigger */}
              {pagination?.has_next && (
                <div ref={observerTarget} className="mt-6 text-center py-8">
                  {loadingMore && (
                    <div className="flex items-center justify-center">
                      <svg className="animate-spin h-8 w-8 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span className="ml-3 text-gray-400">Loading more lands...</span>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default ProfilePage;
