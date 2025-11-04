/**
 * Admin Economy Settings Page
 * Configure economic settings and biome multipliers
 */

import { useState, useEffect } from 'react';
import { adminAPI } from '../services/api';
import useAuthStore from '../stores/authStore';
import toast from 'react-hot-toast';

function AdminEconomyPage() {
  const { user } = useAuthStore();
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user?.role !== 'admin') {
      toast.error('Admin access required');
      return;
    }
    loadSettings();
  }, [user]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const res = await adminAPI.getEconomicSettings();
      setSettings(res.data);
    } catch (error) {
      toast.error('Failed to load economic settings');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminAPI.updateEconomicSettings(settings);
      toast.success('Economic settings updated successfully');
      loadSettings();
    } catch (error) {
      toast.error('Failed to update economic settings');
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (field, value) => {
    setSettings((prev) => ({ ...prev, [field]: value }));
  };

  const handleMultiplierChange = (biome, value) => {
    setSettings((prev) => ({
      ...prev,
      biome_multipliers: {
        ...prev.biome_multipliers,
        [biome]: value,
      },
    }));
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
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold mb-2">Economic Settings</h1>
          <p className="text-gray-400">Configure pricing and transaction fees</p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto p-6">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 space-y-6">
          {/* General Settings */}
          <div>
            <h2 className="text-xl font-bold mb-4">General Settings</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Base Land Price (BDT)
                </label>
                <input
                  type="number"
                  value={settings?.base_land_price_bdt || 0}
                  onChange={(e) => handleChange('base_land_price_bdt', parseInt(e.target.value))}
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Transaction Fee (%)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={settings?.transaction_fee_percent || 0}
                  onChange={(e) => handleChange('transaction_fee_percent', parseFloat(e.target.value))}
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Min Land Price (BDT)
                </label>
                <input
                  type="number"
                  value={settings?.min_land_price_bdt || ''}
                  onChange={(e) => handleChange('min_land_price_bdt', e.target.value ? parseInt(e.target.value) : null)}
                  placeholder="No minimum"
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Max Land Price (BDT)
                </label>
                <input
                  type="number"
                  value={settings?.max_land_price_bdt || ''}
                  onChange={(e) => handleChange('max_land_price_bdt', e.target.value ? parseInt(e.target.value) : null)}
                  placeholder="No maximum"
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div className="mt-4">
              <label className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  checked={settings?.enable_land_trading || false}
                  onChange={(e) => handleChange('enable_land_trading', e.target.checked)}
                  className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <span className="text-sm font-medium text-gray-300">Enable Land Trading</span>
              </label>
            </div>
          </div>

          {/* Biome Multipliers */}
          <div>
            <h2 className="text-xl font-bold mb-4">Biome Price Multipliers</h2>
            <p className="text-sm text-gray-400 mb-4">
              These multipliers are applied to the base land price for each biome type.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {settings?.biome_multipliers &&
                Object.entries(settings.biome_multipliers).map(([biome, multiplier]) => (
                  <div key={biome} className="bg-gray-700 rounded-lg p-4">
                    <label className="block text-sm font-medium text-gray-300 mb-2 capitalize">
                      {biome}
                    </label>
                    <div className="flex items-center space-x-4">
                      <input
                        type="range"
                        min="0.1"
                        max="3.0"
                        step="0.1"
                        value={multiplier}
                        onChange={(e) =>
                          handleMultiplierChange(biome, parseFloat(e.target.value))
                        }
                        className="flex-1 h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer"
                      />
                      <input
                        type="number"
                        step="0.1"
                        value={multiplier}
                        onChange={(e) =>
                          handleMultiplierChange(biome, parseFloat(e.target.value))
                        }
                        className="w-20 bg-gray-600 text-white px-3 py-1 rounded border border-gray-500 focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <p className="text-xs text-gray-400 mt-2">
                      Price: {(settings.base_land_price_bdt * multiplier).toFixed(0)} BDT
                    </p>
                  </div>
                ))}
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end pt-6 border-t border-gray-700">
            <button
              onClick={handleSave}
              disabled={saving}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-8 py-3 rounded font-semibold transition-colors flex items-center space-x-2"
            >
              {saving ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Saving...</span>
                </>
              ) : (
                <span>Save Settings</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminEconomyPage;
