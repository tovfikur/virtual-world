/**
 * Profile Page
 * User profile with stats and owned lands
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { usersAPI } from "../services/api";
import useAuthStore from "../stores/authStore";
import useWorldStore from "../stores/worldStore";
import UserProfileCard from "../components/UserProfileCard";
import TransactionHistory from "../components/TransactionHistory";
import toast from "react-hot-toast";

function ProfilePage() {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const setFocusTarget = useWorldStore((state) => state.setFocusTarget);
  const [stats, setStats] = useState(null);
  const [lands, setLands] = useState([]);
  const [landGroups, setLandGroups] = useState([]);
  const [balance, setBalance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingLands, setLoadingLands] = useState(false);
  const [showTopupModal, setShowTopupModal] = useState(false);
  const [topupAmount, setTopupAmount] = useState(500);
  const [topupGateway, setTopupGateway] = useState("sslcommerz");
  const [topupLoading, setTopupLoading] = useState(false);

  useEffect(() => {
    if (user) {
      loadProfileData();
    } else {
      setLoading(false);
    }
  }, [user]);

  const loadProfileData = async () => {
    try {
      setLoadingLands(true);

      // Load stats and balance first
      const [statsRes, balanceRes] = await Promise.all([
        usersAPI.getUserStats(user.user_id),
        usersAPI.getBalance(user.user_id),
      ]);

      setStats(statsRes.data.stats);
      setBalance(balanceRes.data);
      setLoading(false);

      // Load ALL lands (fetch all pages)
      const allLands = [];
      let currentPage = 1;
      let hasMore = true;

      while (hasMore) {
        const landsRes = await usersAPI.getUserLands(
          user.user_id,
          currentPage,
          100
        );
        allLands.push(...landsRes.data.data);

        hasMore = landsRes.data.pagination.has_next;
        currentPage++;
      }

      setLands(allLands);
      setLoadingLands(false);
    } catch (error) {
      toast.error("Failed to load profile data");
      setLoading(false);
      setLoadingLands(false);
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
            (l) => l.coordinates?.x === x + dx && l.coordinates?.y === y + dy
          );

          if (
            adjacent &&
            !visited.has(`${adjacent.coordinates.x},${adjacent.coordinates.y}`)
          ) {
            findConnected(adjacent, group);
          }
        }
      }
    };

    landsList.forEach((land) => {
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
      console.log(`📊 Grouping ${lands.length} lands into connected groups...`);
      const groups = groupConnectedLands(lands);
      console.log(`✅ Found ${groups.length} land groups`);
      setLandGroups(groups);
    }
  }, [lands, groupConnectedLands]);

  const handleViewOnMap = useCallback(
    (group) => {
      if (!group || group.length === 0) {
        toast.error("No land data available for this group");
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
        toast.error("This group has no map coordinates yet");
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
      const targetZoom = Math.min(
        2,
        Math.max(0.35, 32 / Math.max(maxDimension, 12))
      );

      const focusData = {
        id: Date.now(),
        type: "profile-group",
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

      console.log("🗺️ Setting focus target:", focusData);
      setFocusTarget(focusData);

      toast.success(`Viewing ${group.length} parcels on map`);

      console.log("🧭 Navigating to /world");
      navigate("/world");
    },
    [navigate, setFocusTarget, user]
  );

  const handleTopup = async () => {
    if (!user) return;
    if (!topupAmount || topupAmount < 100) {
      toast.error("Enter at least 100 BDT");
      return;
    }

    try {
      setTopupLoading(true);
      const res = await usersAPI.initiateTopup(
        user.user_id,
        Number(topupAmount),
        topupGateway
      );

      const url = res.data?.payment_url;
      const txn = res.data?.transaction_id;
      toast.success("Payment link ready. Complete checkout to finish top-up.");

      if (url) {
        window.open(url, "_blank", "noopener,noreferrer");
      }

      if (txn) {
        console.log("Top-up transaction id:", txn);
      }

      setShowTopupModal(false);
    } catch (error) {
      const msg =
        error.response?.data?.detail ||
        "Failed to start top-up. Please try again.";
      toast.error(msg);
    } finally {
      setTopupLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Profile Card */}
      <div className="bg-gray-800 border-b border-gray-700 p-4 md:p-6">
        <div className="max-w-7xl mx-auto">
          <UserProfileCard
            user={user}
            isOwnProfile={true}
            isAdmin={user?.role === "admin"}
            onUpdate={(updatedUser) => {
              // Update auth store with new user data
              console.log("Profile updated:", updatedUser);
              // Reload profile data to ensure consistency
              if (user) {
                loadProfileData();
              }
            }}
          />
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-3 md:p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
          {/* Balance Card */}
          <div className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg p-4 md:p-6 shadow-xl">
            <h2 className="text-base md:text-lg font-semibold mb-2 text-blue-100">
              Balance
            </h2>
            <p className="text-3xl md:text-4xl font-bold mb-3 md:mb-4">
              {balance?.balance_bdt || 0} BDT
            </p>
            <button
              onClick={() => setShowTopupModal(true)}
              className="bg-white hover:bg-gray-100 text-blue-900 font-semibold px-3 md:px-4 py-2 rounded-lg transition-colors text-sm md:text-base"
            >
              Top Up
            </button>
          </div>

          {/* Lands Owned */}
          <div className="bg-gray-800 rounded-lg p-4 md:p-6 border border-gray-700">
            <h2 className="text-base md:text-lg font-semibold mb-2 text-gray-300">
              Lands Owned
            </h2>
            <p className="text-3xl md:text-4xl font-bold text-green-400">
              {stats?.lands_owned || 0}
            </p>
            <p className="text-xs md:text-sm text-gray-400 mt-2">
              Total Value: {stats?.total_land_value_bdt || 0} BDT
            </p>
          </div>

          {/* Transactions */}
          <div className="bg-gray-800 rounded-lg p-4 md:p-6 border border-gray-700">
            <h2 className="text-base md:text-lg font-semibold mb-2 text-gray-300">
              Transactions
            </h2>
            <p className="text-3xl md:text-4xl font-bold text-purple-400">
              {stats?.total_transactions || 0}
            </p>
            <p className="text-xs md:text-sm text-gray-400 mt-2">
              {stats?.transactions_as_buyer || 0} buys,{" "}
              {stats?.transactions_as_seller || 0} sales
            </p>
          </div>
        </div>

        {/* Transaction History */}
        <div className="mt-6 md:mt-8">
          <TransactionHistory userId={user.user_id} />
        </div>

        {/* Owned Lands */}
        <div className="mt-6 md:mt-8">
          <div className="flex justify-between items-center mb-3 md:mb-4">
            <h2 className="text-xl md:text-2xl font-bold">My Lands</h2>
            {lands.length > 0 && (
              <p className="text-gray-400">
                {lands.length} {lands.length === 1 ? "land" : "lands"} •{" "}
                {landGroups.length}{" "}
                {landGroups.length === 1 ? "group" : "groups"}
              </p>
            )}
          </div>

          {loadingLands ? (
            <div className="bg-gray-800 rounded-lg p-12 text-center border border-gray-700">
              <div className="flex flex-col items-center justify-center">
                <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-4"></div>
                <p className="text-gray-400 text-lg">Loading your lands...</p>
                <p className="text-gray-500 text-sm mt-2">
                  Calculating connected groups...
                </p>
              </div>
            </div>
          ) : lands.length === 0 ? (
            <div className="bg-gray-800 rounded-lg p-12 text-center border border-gray-700">
              <p className="text-gray-400 text-lg mb-4">
                You don't own any land yet
              </p>
              <a
                href="/marketplace"
                className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
              >
                Browse Marketplace
              </a>
            </div>
          ) : (
            <div className="space-y-3 md:space-y-4">
              {landGroups.map((group, groupIndex) => (
                <div
                  key={groupIndex}
                  className="bg-gray-800 rounded-lg p-4 md:p-6 border border-gray-700 hover:border-blue-500 transition-colors"
                >
                  <div className="flex justify-between items-start mb-3 md:mb-4">
                    <div>
                      <h3 className="text-lg md:text-xl font-bold mb-1">
                        {group.length === 1
                          ? "Single Land Parcel"
                          : `Connected Land Group`}
                      </h3>
                      <p className="text-gray-400 text-xs md:text-sm">
                        {group.length}{" "}
                        {group.length === 1 ? "parcel" : "parcels"} • Total
                        Value:{" "}
                        {group.reduce(
                          (sum, l) => sum + (l.price_base_bdt || 0),
                          0
                        )}{" "}
                        BDT
                      </p>
                    </div>
                    <span className="px-2 md:px-3 py-1 bg-blue-600 text-xs md:text-sm rounded font-semibold">
                      {group.length}x
                    </span>
                  </div>

                  {/* Coordinates Grid */}
                  <div className="mb-4">
                    <p className="text-gray-400 text-xs mb-2 uppercase">
                      Coordinates:
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {group.slice(0, 20).map((land, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-1 bg-gray-700 text-xs rounded font-mono"
                        >
                          ({land.coordinates?.x ?? "?"},{" "}
                          {land.coordinates?.y ?? "?"})
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
                    <p className="text-gray-400 text-xs mb-2 uppercase">
                      Biomes:
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(
                        group.reduce((acc, land) => {
                          const biome = land.biome || "unknown";
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
                  {group.some((l) => l.fenced) && (
                    <div className="mb-4">
                      <span className="px-2 py-1 bg-yellow-600 text-xs rounded">
                        🔒 {group.filter((l) => l.fenced).length} Fenced
                      </span>
                    </div>
                  )}

                  <div className="flex flex-col sm:flex-row gap-2">
                    <button
                      onClick={() => handleViewOnMap(group)}
                      className="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-2 rounded-lg transition-colors text-xs md:text-sm font-semibold flex items-center justify-center gap-2"
                    >
                      <svg
                        className="w-3 h-3 md:w-4 md:h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
                        />
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
          )}
        </div>
      </div>

      {/* Top-up Modal */}
      {showTopupModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 w-full max-w-md shadow-xl">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">Add Funds</h3>
              <button
                onClick={() => setShowTopupModal(false)}
                className="text-gray-400 hover:text-white"
              >
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">
                  Amount (BDT)
                </label>
                <input
                  type="number"
                  min={100}
                  max={100000}
                  value={topupAmount}
                  onChange={(e) => setTopupAmount(Number(e.target.value))}
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-blue-500 text-white"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Min 100, Max 100,000
                </p>
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">
                  Gateway
                </label>
                <select
                  value={topupGateway}
                  onChange={(e) => setTopupGateway(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-blue-500 text-white"
                >
                  <option value="sslcommerz">SSLCommerz</option>
                  <option value="bkash">bKash</option>
                  <option value="nagad">Nagad</option>
                  <option value="rocket">Rocket</option>
                </select>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleTopup}
                  disabled={topupLoading}
                  className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold px-4 py-2 rounded-lg transition-colors"
                >
                  {topupLoading ? "Processing..." : "Start Payment"}
                </button>
                <button
                  onClick={() => setShowTopupModal(false)}
                  className="flex-1 bg-gray-700 hover:bg-gray-600 text-white font-semibold px-4 py-2 rounded-lg transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProfilePage;
