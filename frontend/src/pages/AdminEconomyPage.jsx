/**
 * Admin Economy Settings Page
 * Configure economic settings and biome multipliers
 */

import { useState, useEffect } from "react";
import { adminAPI } from "../services/api";
import useAuthStore from "../stores/authStore";
import toast from "react-hot-toast";

function AdminEconomyPage() {
  const { user } = useAuthStore();
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (user?.role !== "admin") {
      toast.error("Admin access required");
      return;
    }
    loadSettings();
  }, [user]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const res = await adminAPI.getEconomicSettings();
      setSettings(res.data);
      setHasChanges(false);
    } catch (error) {
      toast.error("Failed to load economic settings");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const validateSettings = () => {
    // Validate transaction fee
    if (settings?.transaction_fee_percent < 0 || settings?.transaction_fee_percent > 100) {
      toast.error("Transaction fee must be between 0% and 100%");
      return false;
    }

    // Validate price limits
    if (settings?.min_land_price_bdt && settings?.max_land_price_bdt) {
      if (settings.min_land_price_bdt > settings.max_land_price_bdt) {
        toast.error("Minimum price cannot be greater than maximum price");
        return false;
      }
    }

    // Validate elevation factors
    const elevMin = settings?.elevation_price_factor?.min ?? settings?.elevation_price_min_factor ?? 1;
    const elevMax = settings?.elevation_price_factor?.max ?? settings?.elevation_price_max_factor ?? 2;
    if (elevMin > elevMax) {
      toast.error("Minimum elevation factor cannot be greater than maximum");
      return false;
    }

    // Validate auction durations
    const auctionMin = settings?.auction_limits?.min_duration_hours ?? settings?.auction_min_duration_hours ?? 1;
    const auctionMax = settings?.auction_limits?.max_duration_hours ?? settings?.auction_max_duration_hours ?? 168;
    if (auctionMin > auctionMax) {
      toast.error("Minimum auction duration cannot be greater than maximum");
      return false;
    }

    return true;
  };

  const handleSave = async () => {
    if (!validateSettings()) {
      return;
    }

    setSaving(true);
    try {
      const payload = {
        // General Settings
        base_land_price_bdt: parseInt(settings?.base_land_price_bdt) || 0,
        transaction_fee_percent: parseFloat(settings?.transaction_fee_percent) || 0,
        min_land_price_bdt: settings?.min_land_price_bdt ? parseInt(settings.min_land_price_bdt) : null,
        max_land_price_bdt: settings?.max_land_price_bdt ? parseInt(settings.max_land_price_bdt) : null,
        enable_land_trading: Boolean(settings?.enable_land_trading),

        // Elevation Price Factors
        elevation_price_min_factor:
          parseFloat(settings?.elevation_price_factor?.min ?? settings?.elevation_price_min_factor) || 1,
        elevation_price_max_factor:
          parseFloat(settings?.elevation_price_factor?.max ?? settings?.elevation_price_max_factor) || 2,

        // Biome Land Base Prices
        plains_base_price: parseInt(settings?.biome_land_base_prices?.plains) || 0,
        forest_base_price: parseInt(settings?.biome_land_base_prices?.forest) || 0,
        beach_base_price: parseInt(settings?.biome_land_base_prices?.beach) || 0,
        mountain_base_price: parseInt(settings?.biome_land_base_prices?.mountain) || 0,
        desert_base_price: parseInt(settings?.biome_land_base_prices?.desert) || 0,
        snow_base_price: parseInt(settings?.biome_land_base_prices?.snow) || 0,
        ocean_base_price: parseInt(settings?.biome_land_base_prices?.ocean) || 0,

        // Marketplace Fee Tiers
        fee_tier_1_threshold: parseInt(settings?.marketplace_fee_tiers?.tier_1?.threshold_bdt) || 0,
        fee_tier_1_percent: parseFloat(settings?.marketplace_fee_tiers?.tier_1?.percent) || 0,
        fee_tier_2_threshold: parseInt(settings?.marketplace_fee_tiers?.tier_2?.threshold_bdt) || 0,
        fee_tier_2_percent: parseFloat(settings?.marketplace_fee_tiers?.tier_2?.percent) || 0,
        fee_tier_3_threshold: parseInt(settings?.marketplace_fee_tiers?.tier_3?.threshold_bdt) || 0,
        fee_tier_3_percent: parseFloat(settings?.marketplace_fee_tiers?.tier_3?.percent) || 0,

        // Auction Limits
        auction_min_duration_hours:
          parseInt(settings?.auction_limits?.min_duration_hours ?? settings?.auction_min_duration_hours) || 1,
        auction_max_duration_hours:
          parseInt(settings?.auction_limits?.max_duration_hours ?? settings?.auction_max_duration_hours) || 168,

        // Biome Market Controls
        max_price_move_percent: parseFloat(settings?.biome_market_controls?.max_price_move_percent) || 0,
        max_transaction_percent: parseFloat(settings?.biome_market_controls?.max_transaction_percent) || 0,
        redistribution_pool_percent: parseFloat(settings?.biome_market_controls?.redistribution_pool_percent) || 0,
        biome_trading_paused: Boolean(settings?.biome_market_controls?.biome_trading_paused),
        biome_prices_frozen: Boolean(settings?.biome_market_controls?.biome_prices_frozen),

        // Biome Multipliers (if present)
        ...(settings?.biome_multipliers && Object.keys(settings.biome_multipliers).reduce((acc, biome) => {
          acc[`${biome}_multiplier`] = parseFloat(settings.biome_multipliers[biome]) || 1;
          return acc;
        }, {})),
      };

      await adminAPI.updateEconomicSettings(payload);
      toast.success("Economic settings saved successfully");
      setHasChanges(false);
      loadSettings();
    } catch (error) {
      const message =
        error?.response?.data?.detail || "Failed to update economic settings";
      toast.error(message);
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (field, value) => {
    setSettings((prev) => ({ ...prev, [field]: value }));
    setHasChanges(true);
  };

  const handleMultiplierChange = (biome, value) => {
    setSettings((prev) => ({
      ...prev,
      biome_multipliers: {
        ...prev.biome_multipliers,
        [biome]: value,
      },
    }));
    setHasChanges(true);
  };

  const handleReset = () => {
    if (window.confirm("Are you sure you want to discard all changes?")) {
      loadSettings();
    }
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
    <div className="min-h-screen bg-gray-900 text-white pb-24">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Economic Settings</h1>
              <p className="text-sm text-gray-400 mt-1">
                Configure platform economy, pricing, and trading rules
              </p>
            </div>
            {hasChanges && (
              <div className="flex items-center gap-2 text-sm text-yellow-400">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <span>Unsaved changes</span>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6">
        <div className="space-y-6">
          {/* General Land Pricing */}
          <section className="bg-gray-800 rounded-lg border border-gray-700">
            <div className="border-b border-gray-700 px-6 py-4">
              <h2 className="text-lg font-bold">General Land Pricing</h2>
              <p className="text-sm text-gray-400 mt-1">
                Base pricing and trading configuration for land parcels
              </p>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Base Land Price (BDT) <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={settings?.base_land_price_bdt ?? 0}
                    onChange={(e) =>
                      handleChange("base_land_price_bdt", parseInt(e.target.value) || 0)
                    }
                    className="w-full bg-gray-700 text-white px-4 py-2.5 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Default price for unclaimed land (before biome multipliers)
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Transaction Fee (%) <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={settings?.transaction_fee_percent ?? 0}
                    onChange={(e) =>
                      handleChange("transaction_fee_percent", parseFloat(e.target.value) || 0)
                    }
                    className="w-full bg-gray-700 text-white px-4 py-2.5 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Platform commission on land sales (0-100%)
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Minimum Land Price (BDT)
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={settings?.min_land_price_bdt ?? ""}
                    onChange={(e) =>
                      handleChange("min_land_price_bdt", e.target.value ? parseInt(e.target.value) : null)
                    }
                    placeholder="No minimum (optional)"
                    className="w-full bg-gray-700 text-white px-4 py-2.5 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Lowest allowed price for land transactions
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Maximum Land Price (BDT)
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={settings?.max_land_price_bdt ?? ""}
                    onChange={(e) =>
                      handleChange("max_land_price_bdt", e.target.value ? parseInt(e.target.value) : null)
                    }
                    placeholder="No maximum (optional)"
                    className="w-full bg-gray-700 text-white px-4 py-2.5 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Highest allowed price for land transactions
                  </p>
                </div>
              </div>

              <div className="mt-6 pt-6 border-t border-gray-700">
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings?.enable_land_trading ?? false}
                    onChange={(e) =>
                      handleChange("enable_land_trading", e.target.checked)
                    }
                    className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500 cursor-pointer"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-300">
                      Enable Land Trading
                    </span>
                    <p className="text-xs text-gray-500">
                      Allow users to buy and sell land on the marketplace
                    </p>
                  </div>
                </label>
              </div>
            </div>
          </section>

          {/* Biome Land Base Prices */}
          <section className="bg-gray-800 rounded-lg border border-gray-700">
            <div className="border-b border-gray-700 px-6 py-4">
              <h2 className="text-lg font-bold">Biome Land Base Prices</h2>
              <p className="text-sm text-gray-400 mt-1">
                Initial claim prices for each biome type (overrides base price)
              </p>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {["plains", "forest", "beach", "mountain", "desert", "snow", "ocean"].map((biome) => (
                  <div key={biome} className="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
                    <label className="block text-sm font-medium text-gray-300 mb-2 capitalize flex items-center gap-2">
                      <span className={`w-3 h-3 rounded-full ${
                        biome === 'plains' ? 'bg-green-500' :
                        biome === 'forest' ? 'bg-green-700' :
                        biome === 'beach' ? 'bg-yellow-400' :
                        biome === 'mountain' ? 'bg-gray-500' :
                        biome === 'desert' ? 'bg-yellow-600' :
                        biome === 'snow' ? 'bg-blue-200' :
                        'bg-blue-600'
                      }`}></span>
                      {biome}
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        min="0"
                        step="100"
                        value={settings?.biome_land_base_prices?.[biome] ?? 0}
                        onChange={(e) =>
                          setSettings((prev) => ({
                            ...prev,
                            biome_land_base_prices: {
                              ...prev?.biome_land_base_prices,
                              [biome]: parseInt(e.target.value) || 0,
                            },
                          }))
                        }
                        onBlur={() => setHasChanges(true)}
                        className="flex-1 bg-gray-600 text-white px-3 py-2 rounded border border-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                      <span className="text-sm text-gray-400 font-medium">BDT</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Biome Price Multipliers */}
          {settings?.biome_multipliers && (
            <section className="bg-gray-800 rounded-lg border border-gray-700">
              <div className="border-b border-gray-700 px-6 py-4">
                <h2 className="text-lg font-bold">Biome Price Multipliers</h2>
                <p className="text-sm text-gray-400 mt-1">
                  Multipliers applied to base land price for each biome (legacy system)
                </p>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.entries(settings.biome_multipliers).map(([biome, multiplier]) => (
                    <div key={biome} className="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
                      <label className="block text-sm font-medium text-gray-300 mb-3 capitalize">
                        {biome}
                      </label>
                      <div className="flex items-center gap-4">
                        <input
                          type="range"
                          min="0.1"
                          max="5.0"
                          step="0.1"
                          value={multiplier}
                          onChange={(e) =>
                            handleMultiplierChange(biome, parseFloat(e.target.value))
                          }
                          className="flex-1 h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-blue-500"
                        />
                        <input
                          type="number"
                          min="0.1"
                          max="5.0"
                          step="0.1"
                          value={multiplier}
                          onChange={(e) =>
                            handleMultiplierChange(biome, parseFloat(e.target.value) || 0.1)
                          }
                          className="w-20 bg-gray-600 text-white px-3 py-1.5 rounded border border-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 text-center"
                        />
                        <span className="text-xs text-gray-400">×</span>
                      </div>
                      <p className="text-xs text-gray-500 mt-2">
                        Calculated price: {(settings.base_land_price_bdt * multiplier).toFixed(0)} BDT
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {/* Elevation Price Factors */}
          <section className="bg-gray-800 rounded-lg border border-gray-700">
            <div className="border-b border-gray-700 px-6 py-4">
              <h2 className="text-lg font-bold">Elevation Price Factors</h2>
              <p className="text-sm text-gray-400 mt-1">
                Price adjustment multipliers based on land elevation
              </p>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Minimum Factor
                  </label>
                  <input
                    type="number"
                    min="0.1"
                    max="10"
                    step="0.1"
                    value={
                      settings?.elevation_price_factor?.min ??
                      settings?.elevation_price_min_factor ??
                      1
                    }
                    onChange={(e) => {
                      const value = parseFloat(e.target.value) || 1;
                      setSettings((prev) => ({
                        ...prev,
                        elevation_price_factor: {
                          min: value,
                          max:
                            prev?.elevation_price_factor?.max ??
                            prev?.elevation_price_max_factor ??
                            2,
                        },
                      }));
                      setHasChanges(true);
                    }}
                    className="w-full bg-gray-700 text-white px-4 py-2.5 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Multiplier for lowest elevation lands
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Maximum Factor
                  </label>
                  <input
                    type="number"
                    min="0.1"
                    max="10"
                    step="0.1"
                    value={
                      settings?.elevation_price_factor?.max ??
                      settings?.elevation_price_max_factor ??
                      2
                    }
                    onChange={(e) => {
                      const value = parseFloat(e.target.value) || 2;
                      setSettings((prev) => ({
                        ...prev,
                        elevation_price_factor: {
                          min:
                            prev?.elevation_price_factor?.min ??
                            prev?.elevation_price_min_factor ??
                            1,
                          max: value,
                        },
                      }));
                      setHasChanges(true);
                    }}
                    className="w-full bg-gray-700 text-white px-4 py-2.5 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Multiplier for highest elevation lands
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Marketplace Fee Tiers */}
          <section className="bg-gray-800 rounded-lg border border-gray-700">
            <div className="border-b border-gray-700 px-6 py-4">
              <h2 className="text-lg font-bold">Marketplace Fee Tiers</h2>
              <p className="text-sm text-gray-400 mt-1">
                Tiered fee structure for marketplace transactions
              </p>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {["tier_1", "tier_2", "tier_3"].map((tier, index) => (
                  <div key={tier} className="bg-gray-700/50 rounded-lg p-4 border border-gray-600">
                    <h3 className="font-semibold mb-4 text-blue-400 capitalize">
                      Tier {index + 1}
                    </h3>
                    <div className="space-y-4">
                      <div>
                        <label className="block text-xs font-medium text-gray-400 mb-2">
                          Threshold (BDT)
                        </label>
                        <input
                          type="number"
                          min="0"
                          value={
                            settings?.marketplace_fee_tiers?.[tier]?.threshold_bdt ?? 0
                          }
                          onChange={(e) => {
                            setSettings((prev) => ({
                              ...prev,
                              marketplace_fee_tiers: {
                                ...prev.marketplace_fee_tiers,
                                [tier]: {
                                  ...prev.marketplace_fee_tiers?.[tier],
                                  threshold_bdt: parseInt(e.target.value, 10) || 0,
                                },
                              },
                            }));
                            setHasChanges(true);
                          }}
                          className="w-full bg-gray-600 text-white px-3 py-2 rounded border border-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-400 mb-2">
                          Fee Percent (%)
                        </label>
                        <input
                          type="number"
                          min="0"
                          max="100"
                          step="0.1"
                          value={
                            settings?.marketplace_fee_tiers?.[tier]?.percent ?? 0
                          }
                          onChange={(e) => {
                            setSettings((prev) => ({
                              ...prev,
                              marketplace_fee_tiers: {
                                ...prev.marketplace_fee_tiers,
                                [tier]: {
                                  ...prev.marketplace_fee_tiers?.[tier],
                                  percent: parseFloat(e.target.value) || 0,
                                },
                              },
                            }));
                            setHasChanges(true);
                          }}
                          className="w-full bg-gray-600 text-white px-3 py-2 rounded border border-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Auction Limits */}
          <section className="bg-gray-800 rounded-lg border border-gray-700">
            <div className="border-b border-gray-700 px-6 py-4">
              <h2 className="text-lg font-bold">Auction Duration Limits</h2>
              <p className="text-sm text-gray-400 mt-1">
                Minimum and maximum allowed auction durations
              </p>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Minimum Duration (hours)
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={
                      settings?.auction_limits?.min_duration_hours ??
                      settings?.auction_min_duration_hours ??
                      1
                    }
                    onChange={(e) => {
                      setSettings((prev) => ({
                        ...prev,
                        auction_limits: {
                          min_duration_hours: parseInt(e.target.value, 10) || 1,
                          max_duration_hours:
                            prev?.auction_limits?.max_duration_hours ??
                            prev?.auction_max_duration_hours ??
                            168,
                        },
                      }));
                      setHasChanges(true);
                    }}
                    className="w-full bg-gray-700 text-white px-4 py-2.5 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Shortest allowed auction duration
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Maximum Duration (hours)
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={
                      settings?.auction_limits?.max_duration_hours ??
                      settings?.auction_max_duration_hours ??
                      168
                    }
                    onChange={(e) => {
                      setSettings((prev) => ({
                        ...prev,
                        auction_limits: {
                          min_duration_hours:
                            prev?.auction_limits?.min_duration_hours ??
                            prev?.auction_min_duration_hours ??
                            1,
                          max_duration_hours: parseInt(e.target.value, 10) || 168,
                        },
                      }));
                      setHasChanges(true);
                    }}
                    className="w-full bg-gray-700 text-white px-4 py-2.5 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Longest allowed auction duration (168h = 7 days)
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Biome Market Controls */}
          <section className="bg-gray-800 rounded-lg border border-gray-700">
            <div className="border-b border-gray-700 px-6 py-4">
              <h2 className="text-lg font-bold">Biome Market Controls</h2>
              <p className="text-sm text-gray-400 mt-1">
                Configure biome share trading and price movement limits
              </p>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Max Price Move (%)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={
                      settings?.biome_market_controls?.max_price_move_percent ?? 0
                    }
                    onChange={(e) => {
                      setSettings((prev) => ({
                        ...prev,
                        biome_market_controls: {
                          ...prev.biome_market_controls,
                          max_price_move_percent: parseFloat(e.target.value) || 0,
                        },
                      }));
                      setHasChanges(true);
                    }}
                    className="w-full bg-gray-700 text-white px-4 py-2.5 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Maximum allowed price change per update
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Max Transaction (% of cap)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={
                      settings?.biome_market_controls?.max_transaction_percent ?? 0
                    }
                    onChange={(e) => {
                      setSettings((prev) => ({
                        ...prev,
                        biome_market_controls: {
                          ...prev.biome_market_controls,
                          max_transaction_percent: parseFloat(e.target.value) || 0,
                        },
                      }));
                      setHasChanges(true);
                    }}
                    className="w-full bg-gray-700 text-white px-4 py-2.5 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Max single transaction size vs market cap
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Redistribution Pool (%)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={
                      settings?.biome_market_controls?.redistribution_pool_percent ?? 0
                    }
                    onChange={(e) => {
                      setSettings((prev) => ({
                        ...prev,
                        biome_market_controls: {
                          ...prev.biome_market_controls,
                          redistribution_pool_percent: parseFloat(e.target.value) || 0,
                        },
                      }));
                      setHasChanges(true);
                    }}
                    className="w-full bg-gray-700 text-white px-4 py-2.5 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Percentage allocated to redistribution
                  </p>
                </div>
              </div>
              <div className="mt-6 pt-6 border-t border-gray-700 space-y-4">
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={
                      settings?.biome_market_controls?.biome_trading_paused ?? false
                    }
                    onChange={(e) => {
                      setSettings((prev) => ({
                        ...prev,
                        biome_market_controls: {
                          ...prev.biome_market_controls,
                          biome_trading_paused: e.target.checked,
                        },
                      }));
                      setHasChanges(true);
                    }}
                    className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500 cursor-pointer"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-300">
                      Pause Biome Trading
                    </span>
                    <p className="text-xs text-gray-500">
                      Temporarily disable all biome share transactions
                    </p>
                  </div>
                </label>
                <label className="flex items-center space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={
                      settings?.biome_market_controls?.biome_prices_frozen ?? false
                    }
                    onChange={(e) => {
                      setSettings((prev) => ({
                        ...prev,
                        biome_market_controls: {
                          ...prev.biome_market_controls,
                          biome_prices_frozen: e.target.checked,
                        },
                      }));
                      setHasChanges(true);
                    }}
                    className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500 cursor-pointer"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-300">
                      Freeze Biome Prices
                    </span>
                    <p className="text-xs text-gray-500">
                      Stop automatic price redistribution and updates
                    </p>
                  </div>
                </label>
              </div>
            </div>
          </section>
        </div>
      </div>

      {/* Sticky Save/Cancel Bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-gray-800 border-t border-gray-700 shadow-lg">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            {hasChanges && (
              <div className="flex items-center gap-2 text-sm text-yellow-400">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                <span>You have unsaved changes</span>
              </div>
            )}
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleReset}
              disabled={saving || !hasChanges}
              className="px-6 py-2.5 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
            >
              Reset
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !hasChanges}
              className="px-8 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg font-semibold transition-colors flex items-center gap-2 shadow-lg"
            >
              {saving ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span>Save All Changes</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminEconomyPage;
