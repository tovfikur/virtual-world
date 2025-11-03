/**
 * Profile Page
 * User profile with stats and owned lands
 */

import { useState, useEffect } from 'react';
import { usersAPI } from '../services/api';
import useAuthStore from '../stores/authStore';
import toast from 'react-hot-toast';

function ProfilePage() {
  const { user } = useAuthStore();
  const [stats, setStats] = useState(null);
  const [lands, setLands] = useState([]);
  const [balance, setBalance] = useState(null);
  const [loading, setLoading] = useState(true);

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
        usersAPI.getUserLands(user.user_id, 1, 10),
        usersAPI.getBalance(user.user_id)
      ]);

      setStats(statsRes.data.stats);
      setLands(landsRes.data.data);
      setBalance(balanceRes.data);
    } catch (error) {
      toast.error('Failed to load profile data');
    } finally {
      setLoading(false);
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
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-2">{user.username}</h1>
          <p className="text-gray-400">{user.email}</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Balance Card */}
          <div className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg p-6 shadow-xl">
            <h2 className="text-lg font-semibold mb-2 text-blue-100">Balance</h2>
            <p className="text-4xl font-bold mb-4">{balance?.balance_bdt || 0} BDT</p>
            <button className="bg-white hover:bg-gray-100 text-blue-900 font-semibold px-4 py-2 rounded-lg transition-colors">
              Top Up
            </button>
          </div>

          {/* Lands Owned */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h2 className="text-lg font-semibold mb-2 text-gray-300">Lands Owned</h2>
            <p className="text-4xl font-bold text-green-400">{stats?.lands_owned || 0}</p>
            <p className="text-sm text-gray-400 mt-2">
              Total Value: {stats?.total_land_value_bdt || 0} BDT
            </p>
          </div>

          {/* Transactions */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h2 className="text-lg font-semibold mb-2 text-gray-300">Transactions</h2>
            <p className="text-4xl font-bold text-purple-400">{stats?.total_transactions || 0}</p>
            <p className="text-sm text-gray-400 mt-2">
              {stats?.transactions_as_buyer || 0} buys, {stats?.transactions_as_seller || 0} sales
            </p>
          </div>
        </div>

        {/* Owned Lands */}
        <div className="mt-8">
          <h2 className="text-2xl font-bold mb-4">My Lands</h2>
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
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {lands.map((land) => (
                <div
                  key={land.land_id}
                  className="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-blue-500 transition-colors"
                >
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <p className="text-gray-400 text-sm">Land</p>
                      <p className="font-semibold">({land.x}, {land.y})</p>
                    </div>
                    <span className="px-2 py-1 bg-blue-600 text-xs rounded capitalize">
                      {land.biome}
                    </span>
                  </div>

                  <div className="mb-3">
                    <p className="text-gray-400 text-sm">Base Price</p>
                    <p className="text-xl font-bold text-green-400">
                      {land.price_base_bdt} BDT
                    </p>
                  </div>

                  {land.fenced && (
                    <div className="mb-3">
                      <span className="px-2 py-1 bg-yellow-600 text-xs rounded">
                        🔒 Fenced
                      </span>
                    </div>
                  )}

                  <button className="w-full bg-gray-700 hover:bg-gray-600 text-white py-2 rounded-lg transition-colors text-sm">
                    View Details
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ProfilePage;
