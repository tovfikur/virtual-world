/**
 * Admin Configuration Page
 * Manage world settings and system configuration
 */

import { useState, useEffect } from 'react';
import { adminAPI } from '../services/api';
import useAuthStore from '../stores/authStore';
import toast from 'react-hot-toast';

function AdminConfigPage() {
  const { user } = useAuthStore();
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState({});

  useEffect(() => {
    if (user?.role === 'admin') {
      loadConfig();
    }
  }, [user]);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const response = await adminAPI.getWorldConfig();
      setConfig(response.data);
      if (response.data.config) {
        setEditData({
          default_world_seed: response.data.config.default_world_seed,
          enable_maintenance_mode: response.data.config.maintenance_mode
        });
      }
    } catch (error) {
      toast.error('Failed to load configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      await adminAPI.updateWorldConfig(editData);
      toast.success('Configuration updated successfully');
      setEditMode(false);
      loadConfig();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update configuration');
    }
  };

  if (user?.role !== 'admin') {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-400 mb-4">Access Denied</h1>
          <p className="text-gray-400">Admin access required</p>
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
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold mb-2">World Configuration</h1>
          <p className="text-gray-400">Manage world generation and system settings</p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto p-6">
        {/* World Generation Settings */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-bold">World Generation</h2>
            {!editMode ? (
              <button
                onClick={() => setEditMode(true)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors font-semibold"
              >
                Edit Settings
              </button>
            ) : (
              <div className="flex space-x-2">
                <button
                  onClick={handleSave}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors font-semibold"
                >
                  Save
                </button>
                <button
                  onClick={() => {
                    setEditMode(false);
                    loadConfig();
                  }}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>

          <div className="space-y-6">
            {/* World Seed */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                World Seed
              </label>
              {editMode ? (
                <input
                  type="number"
                  value={editData.default_world_seed || ''}
                  onChange={(e) => setEditData({ ...editData, default_world_seed: parseInt(e.target.value) })}
                  className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
                />
              ) : (
                <p className="text-lg font-semibold text-blue-400">
                  {config?.config?.default_world_seed || 'Not set'}
                </p>
              )}
              <p className="text-sm text-gray-500 mt-1">
                Deterministic seed for world generation. Changing this will regenerate the entire world.
              </p>
            </div>

            {/* Maintenance Mode */}
            <div className="flex items-center justify-between">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Maintenance Mode
                </label>
                <p className="text-sm text-gray-500">
                  When enabled, only admins can access the platform
                </p>
              </div>
              {editMode ? (
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editData.enable_maintenance_mode || false}
                    onChange={(e) => setEditData({ ...editData, enable_maintenance_mode: e.target.checked })}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              ) : (
                <span className={`px-3 py-1 rounded font-semibold text-sm ${
                  config?.config?.maintenance_mode ? 'bg-red-600' : 'bg-green-600'
                }`}>
                  {config?.config?.maintenance_mode ? 'Enabled' : 'Disabled'}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Trading Settings */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
          <h2 className="text-xl font-bold mb-4">Trading Settings</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Land Trading</p>
                <p className="text-sm text-gray-500">Allow users to buy and sell land</p>
              </div>
              <span className={`px-3 py-1 rounded font-semibold text-sm ${
                config?.config?.enable_land_trading ? 'bg-green-600' : 'bg-red-600'
              }`}>
                {config?.config?.enable_land_trading ? 'Enabled' : 'Disabled'}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-4">
              <div>
                <p className="text-sm text-gray-400 mb-1">Minimum Land Price</p>
                <p className="text-lg font-semibold text-green-400">
                  {config?.config?.min_land_price_bdt?.toLocaleString() || 'Not set'} BDT
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-400 mb-1">Maximum Land Price</p>
                <p className="text-lg font-semibold text-green-400">
                  {config?.config?.max_land_price_bdt?.toLocaleString() || 'Not set'} BDT
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Chat Settings */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
          <h2 className="text-xl font-bold mb-4">Communication Settings</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Chat System</p>
                <p className="text-sm text-gray-500">Allow users to send messages</p>
              </div>
              <span className={`px-3 py-1 rounded font-semibold text-sm ${
                config?.config?.enable_chat ? 'bg-green-600' : 'bg-red-600'
              }`}>
                {config?.config?.enable_chat ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          </div>
        </div>

        {/* Auction Settings */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <h2 className="text-xl font-bold mb-4">Auction Settings</h2>
          <div>
            <p className="text-sm text-gray-400 mb-1">Auto-Extend Duration</p>
            <p className="text-lg font-semibold">
              {config?.config?.auction_extend_minutes || 'Not set'} minutes
            </p>
            <p className="text-sm text-gray-500 mt-1">
              When a bid is placed in the last X minutes, the auction extends by this amount
            </p>
          </div>
        </div>

        {/* Warning */}
        {editMode && (
          <div className="mt-6 bg-yellow-900/30 border border-yellow-700 rounded-lg p-4">
            <div className="flex items-start space-x-3">
              <svg className="w-6 h-6 text-yellow-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <p className="font-semibold text-yellow-200">Warning</p>
                <p className="text-sm text-yellow-300 mt-1">
                  Changing critical settings like the world seed will affect all users. Make sure you understand the implications before saving.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default AdminConfigPage;
