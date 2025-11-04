/**
 * Admin Land Management Page
 * View land analytics and perform land administration
 */

import { useState, useEffect } from 'react';
import { adminAPI } from '../services/api';
import useAuthStore from '../stores/authStore';
import toast from 'react-hot-toast';

function AdminLandsPage() {
  const { user } = useAuthStore();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('analytics');

  useEffect(() => {
    if (user?.role !== 'admin') {
      toast.error('Admin access required');
      return;
    }
    loadAnalytics();
  }, [user]);

  const loadAnalytics = async () => {
    setLoading(true);
    try {
      const res = await adminAPI.getLandAnalytics();
      setAnalytics(res.data);
    } catch (error) {
      toast.error('Failed to load land analytics');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleTransferLand = async () => {
    const landId = prompt('Enter Land ID to transfer:');
    if (!landId) return;

    const newOwnerId = prompt('Enter New Owner User ID:');
    if (!newOwnerId) return;

    const reason = prompt('Enter reason for transfer:');
    if (!reason) return;

    try {
      await adminAPI.transferLand(landId, newOwnerId, reason);
      toast.success('Land transferred successfully');
      loadAnalytics();
    } catch (error) {
      toast.error('Failed to transfer land');
      console.error(error);
    }
  };

  const handleReclaimLand = async () => {
    const landId = prompt('Enter Land ID to reclaim:');
    if (!landId) return;

    const reason = prompt('Enter reason for reclaiming:');
    if (!reason) return;

    const confirmed = window.confirm('Are you sure you want to reclaim this land? This action cannot be undone.');
    if (!confirmed) return;

    try {
      await adminAPI.reclaimLand(landId, reason);
      toast.success('Land reclaimed successfully');
      loadAnalytics();
    } catch (error) {
      toast.error('Failed to reclaim land');
      console.error(error);
    }
  };

  if (user?.role !== 'admin') {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-400 mb-4">Access Denied</h1>
          <p className="text-gray-400">You need admin privileges to access this page.</p>
        </div>
      </div>
    );
  }

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
          <h1 className="text-3xl font-bold mb-2">Land Management</h1>
          <p className="text-gray-400">View land analytics and manage land ownership</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {/* Tabs */}
        <div className="flex space-x-4 mb-6 border-b border-gray-700">
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === 'analytics'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
            onClick={() => setActiveTab('analytics')}
          >
            Analytics
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === 'administration'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
            onClick={() => setActiveTab('administration')}
          >
            Administration
          </button>
        </div>

        {activeTab === 'analytics' && analytics && (
          <div>
            {/* Statistics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <div className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg p-6 shadow-xl">
                <h3 className="text-lg font-semibold mb-2">Total Lands</h3>
                <p className="text-3xl font-bold">{analytics.total_lands.toLocaleString()}</p>
              </div>

              <div className="bg-gradient-to-br from-green-600 to-green-800 rounded-lg p-6 shadow-xl">
                <h3 className="text-lg font-semibold mb-2">Allocated</h3>
                <p className="text-3xl font-bold">{analytics.allocated_lands.toLocaleString()}</p>
                <p className="text-sm opacity-75 mt-2">
                  {((analytics.allocated_lands / analytics.total_lands) * 100).toFixed(1)}% of total
                </p>
              </div>

              <div className="bg-gradient-to-br from-purple-600 to-purple-800 rounded-lg p-6 shadow-xl">
                <h3 className="text-lg font-semibold mb-2">Unallocated</h3>
                <p className="text-3xl font-bold">{analytics.unallocated_lands.toLocaleString()}</p>
              </div>

              <div className="bg-gradient-to-br from-yellow-600 to-yellow-800 rounded-lg p-6 shadow-xl">
                <h3 className="text-lg font-semibold mb-2">For Sale</h3>
                <p className="text-3xl font-bold">{analytics.lands_for_sale.toLocaleString()}</p>
              </div>
            </div>

            {/* Biome Distribution */}
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
              <h2 className="text-xl font-bold mb-4">Biome Distribution</h2>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {Object.entries(analytics.biome_distribution || {}).map(([biome, count]) => (
                  <div key={biome} className="bg-gray-700 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-blue-400">{count.toLocaleString()}</p>
                    <p className="text-sm text-gray-400 capitalize mt-1">{biome}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Shape Distribution */}
            {analytics.shape_distribution && Object.keys(analytics.shape_distribution).length > 0 && (
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h2 className="text-xl font-bold mb-4">Shape Distribution</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(analytics.shape_distribution).map(([shape, count]) => (
                    <div key={shape} className="bg-gray-700 rounded-lg p-4 text-center">
                      <p className="text-2xl font-bold text-green-400">{count.toLocaleString()}</p>
                      <p className="text-sm text-gray-400 capitalize mt-1">{shape}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'administration' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Transfer Land */}
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h3 className="text-xl font-bold mb-4">Transfer Land Ownership</h3>
              <p className="text-gray-400 mb-4">
                Transfer a land plot from one user to another. This is a permanent action.
              </p>
              <button
                onClick={handleTransferLand}
                className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded font-semibold transition-colors w-full"
              >
                Transfer Land
              </button>
            </div>

            {/* Reclaim Land */}
            <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
              <h3 className="text-xl font-bold mb-4">Reclaim Land</h3>
              <p className="text-gray-400 mb-4">
                Reclaim a land plot and make it available for reallocation. Use with caution.
              </p>
              <button
                onClick={handleReclaimLand}
                className="bg-red-600 hover:bg-red-700 px-6 py-3 rounded font-semibold transition-colors w-full"
              >
                Reclaim Land
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default AdminLandsPage;
