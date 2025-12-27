/**
 * Admin Features & Limits Configuration Page
 * Configure feature toggles and system limits
 */

import { useState, useEffect } from "react";
import { adminAPI } from "../services/api";
import useAuthStore from "../stores/authStore";
import toast from "react-hot-toast";

function AdminFeaturesPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState("features");
  const [features, setFeatures] = useState(null);
  const [limits, setLimits] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user?.role !== "admin") {
      toast.error("Admin access required");
      return;
    }
    loadData();
  }, [user, activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === "features") {
        const res = await adminAPI.getFeatureToggles();
        setFeatures(res.data);
      } else if (activeTab === "limits") {
        const res = await adminAPI.getSystemLimits();
        setLimits(res.data);
      }
    } catch (error) {
      toast.error("Failed to load configuration");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveFeatures = async () => {
    setSaving(true);
    try {
      await adminAPI.updateFeatureToggles(features);
      toast.success("Feature toggles updated successfully");
      loadData();
    } catch (error) {
      toast.error("Failed to update feature toggles");
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveLimits = async () => {
    setSaving(true);
    try {
      await adminAPI.updateSystemLimits(limits);
      toast.success("System limits updated successfully");
      loadData();
    } catch (error) {
      toast.error("Failed to update system limits");
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  const handleFeatureToggle = (key) => {
    setFeatures((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleLimitChange = (key, value) => {
    setLimits((prev) => ({ ...prev, [key]: value }));
  };

  if (user?.role !== "admin") {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-400 mb-4">
            Access Denied
          </h1>
          <p className="text-gray-400">
            You need admin privileges to access this page.
          </p>
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
          <h1 className="text-3xl font-bold mb-2">System Configuration</h1>
          <p className="text-gray-400">
            Configure feature toggles and system limits
          </p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto p-6">
        {/* Tabs */}
        <div className="flex space-x-4 mb-6 border-b border-gray-700">
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "features"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => setActiveTab("features")}
          >
            Feature Toggles
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "limits"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => setActiveTab("limits")}
          >
            System Limits
          </button>
        </div>

        {activeTab === "features" && features && (
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h2 className="text-xl font-bold mb-6">Feature Toggles</h2>

            <div className="space-y-6">
              {/* Land Trading */}
              <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
                <div>
                  <h3 className="font-semibold mb-1">Land Trading</h3>
                  <p className="text-sm text-gray-400">
                    Allow users to buy and sell land on the marketplace
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={features.enable_land_trading}
                    onChange={() => handleFeatureToggle("enable_land_trading")}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              {/* Chat System */}
              <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
                <div>
                  <h3 className="font-semibold mb-1">Chat System</h3>
                  <p className="text-sm text-gray-400">
                    Enable in-game chat functionality
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={features.enable_chat}
                    onChange={() => handleFeatureToggle("enable_chat")}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              {/* User Registration */}
              <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
                <div>
                  <h3 className="font-semibold mb-1">User Registration</h3>
                  <p className="text-sm text-gray-400">
                    Allow new users to register accounts
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={features.enable_registration}
                    onChange={() => handleFeatureToggle("enable_registration")}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              {/* Starter Land Allocation */}
              <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
                <div>
                  <h3 className="font-semibold mb-1">
                    Starter Land Allocation
                  </h3>
                  <p className="text-sm text-gray-400">
                    Automatically allocate land to new users
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={features.starter_land_enabled}
                    onChange={() => handleFeatureToggle("starter_land_enabled")}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              {/* Maintenance Mode */}
              <div className="flex items-center justify-between p-4 bg-red-900 bg-opacity-20 border border-red-700 rounded-lg">
                <div>
                  <h3 className="font-semibold mb-1 text-red-400">
                    Maintenance Mode
                  </h3>
                  <p className="text-sm text-gray-400">
                    Block all non-admin users from accessing the platform
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={features.maintenance_mode}
                    onChange={() => handleFeatureToggle("maintenance_mode")}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600"></div>
                </label>
              </div>
            </div>

            {/* Save Button */}
            <div className="flex justify-end pt-6 border-t border-gray-700 mt-6">
              <button
                onClick={handleSaveFeatures}
                disabled={saving}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-8 py-3 rounded font-semibold transition-colors"
              >
                {saving ? "Saving..." : "Save Feature Toggles"}
              </button>
            </div>
          </div>
        )}

        {activeTab === "limits" && limits && (
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h2 className="text-xl font-bold mb-6">System Limits</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Max Lands Per User */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Max Lands Per User
                </label>
                <input
                  type="number"
                  value={limits.max_lands_per_user || ""}
                  onChange={(e) =>
                    handleLimitChange(
                      "max_lands_per_user",
                      e.target.value ? parseInt(e.target.value) : null
                    )
                  }
                  placeholder="No limit"
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Leave empty for no limit
                </p>
              </div>

              {/* Max Listings Per User */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Max Listings Per User
                </label>
                <input
                  type="number"
                  value={limits.max_listings_per_user || ""}
                  onChange={(e) =>
                    handleLimitChange(
                      "max_listings_per_user",
                      parseInt(e.target.value)
                    )
                  }
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Auction Bid Increment */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Auction Bid Increment (BDT)
                </label>
                <input
                  type="number"
                  value={limits.auction_bid_increment || ""}
                  onChange={(e) =>
                    handleLimitChange(
                      "auction_bid_increment",
                      parseInt(e.target.value)
                    )
                  }
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Auction Extend Minutes */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Auction Auto-Extend (Minutes)
                </label>
                <input
                  type="number"
                  value={limits.auction_extend_minutes || ""}
                  onChange={(e) =>
                    handleLimitChange(
                      "auction_extend_minutes",
                      parseInt(e.target.value)
                    )
                  }
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Time to extend auction after late bid
                </p>
              </div>

              {/* Rate Limiting - API */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  API Rate Limit (requests/min)
                </label>
                <input
                  type="number"
                  value={limits.rate_limit_api_per_minute || ""}
                  onChange={(e) =>
                    handleLimitChange(
                      "rate_limit_api_per_minute",
                      parseInt(e.target.value)
                    )
                  }
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Rate Limiting - Marketplace */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Marketplace Rate Limit (requests/min)
                </label>
                <input
                  type="number"
                  value={limits.rate_limit_marketplace_per_minute || ""}
                  onChange={(e) =>
                    handleLimitChange(
                      "rate_limit_marketplace_per_minute",
                      parseInt(e.target.value)
                    )
                  }
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Rate Limiting - Chat */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Chat Rate Limit (messages/min)
                </label>
                <input
                  type="number"
                  value={limits.rate_limit_chat_per_minute || ""}
                  onChange={(e) =>
                    handleLimitChange(
                      "rate_limit_chat_per_minute",
                      parseInt(e.target.value)
                    )
                  }
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Rate Limiting - Biome Trades */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Biome Trades Rate Limit (ops/min)
                </label>
                <input
                  type="number"
                  value={limits.rate_limit_biome_trades_per_minute || ""}
                  onChange={(e) =>
                    handleLimitChange(
                      "rate_limit_biome_trades_per_minute",
                      parseInt(e.target.value)
                    )
                  }
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Save Button */}
            <div className="flex justify-end pt-6 border-t border-gray-700 mt-6">
              <button
                onClick={handleSaveLimits}
                disabled={saving}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-8 py-3 rounded font-semibold transition-colors"
              >
                {saving ? "Saving..." : "Save System Limits"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default AdminFeaturesPage;
