import { useEffect, useState } from "react";
import { adminAPI } from "../services/api";
import useAuthStore from "../stores/authStore";
import toast from "react-hot-toast";

function AdminTestingDebugPage() {
  const { user } = useAuthStore();
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

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
      const res = await adminAPI.getTestingDebugSettings();
      setSettings(res.data.testing_debugging);
    } catch (error) {
      toast.error("Failed to load testing/debug settings");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const toggle = (section, key) => {
    setSettings((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: !prev[section][key],
      },
    }));
  };

  const updateValue = (section, key, value) => {
    setSettings((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value,
      },
    }));
  };

  const numOrUndefined = (val) => {
    const n = Number(val);
    return Number.isFinite(n) ? n : undefined;
  };

  const handleSave = async () => {
    if (!settings) return;

    // Client-side guardrails
    const td = settings.test_data_generation || {};
    const perf = settings.performance_testing || {};
    const split = Number(settings.ab_testing?.split_percent ?? 0);

    if (td.users_count < 1 || td.lands_count < 1 || td.listings_count < 1) {
      toast.error("Test data counts must be at least 1");
      return;
    }
    if (split < 0 || split > 100) {
      toast.error("A/B split percent must be between 0 and 100");
      return;
    }
    if (perf.concurrent_users < 1 || perf.requests_per_second < 1) {
      toast.error("Performance test users/RPS must be at least 1");
      return;
    }

    const payload = {
      test_data_generation_enabled: settings.test_data_generation?.enabled,
      test_data_users_count: numOrUndefined(
        settings.test_data_generation?.users_count
      ),
      test_data_lands_count: numOrUndefined(
        settings.test_data_generation?.lands_count
      ),
      test_data_listings_count: numOrUndefined(
        settings.test_data_generation?.listings_count
      ),
      test_data_market_activity_enabled:
        settings.test_data_generation?.market_activity_enabled,
      feature_flags_enabled: settings.feature_flags?.enabled,
      ab_testing_enabled: settings.ab_testing?.enabled,
      ab_test_split_percent: numOrUndefined(settings.ab_testing?.split_percent),
      ab_test_variant_id: settings.ab_testing?.variant_id,
      debug_session_inspect_enabled:
        settings.debug_tools?.session_inspect_enabled,
      debug_redis_inspect_enabled: settings.debug_tools?.redis_inspect_enabled,
      debug_websocket_connections_enabled:
        settings.debug_tools?.websocket_connections_enabled,
      debug_verbose_logging_enabled:
        settings.debug_tools?.verbose_logging_enabled,
      perf_test_enabled: settings.performance_testing?.enabled,
      perf_test_concurrent_users: numOrUndefined(
        settings.performance_testing?.concurrent_users
      ),
      perf_test_requests_per_second: numOrUndefined(
        settings.performance_testing?.requests_per_second
      ),
    };

    setSaving(true);
    try {
      await adminAPI.updateTestingDebugSettings(payload);
      toast.success("Testing/Debug settings updated");
      loadSettings();
    } catch (error) {
      const message =
        error?.response?.data?.detail || "Failed to update settings";
      toast.error(message);
      console.error(error);
    } finally {
      setSaving(false);
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

  if (loading || !settings) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="bg-gray-800 border-b border-gray-700 p-6">
        <div className="max-w-5xl mx-auto">
          <h1 className="text-3xl font-bold mb-2">
            Testing & Debugging Controls
          </h1>
          <p className="text-gray-400">
            Manage test data generation, feature flags, debug tools, and
            performance testing
          </p>
        </div>
      </div>

      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {/* Test Data Generation */}
        <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold">Test Data Generation</h2>
              <p className="text-sm text-gray-400">
                Seed users, lands, listings, and market activity for QA
              </p>
            </div>
            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={settings.test_data_generation?.enabled || false}
                onChange={() => toggle("test_data_generation", "enabled")}
                className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
              />
              <span className="text-sm text-gray-300">Enable</span>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Users Count
              </label>
              <input
                type="number"
                min="1"
                value={settings.test_data_generation?.users_count ?? 1}
                onChange={(e) =>
                  updateValue(
                    "test_data_generation",
                    "users_count",
                    parseInt(e.target.value, 10)
                  )
                }
                className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Lands Count
              </label>
              <input
                type="number"
                min="1"
                value={settings.test_data_generation?.lands_count ?? 1}
                onChange={(e) =>
                  updateValue(
                    "test_data_generation",
                    "lands_count",
                    parseInt(e.target.value, 10)
                  )
                }
                className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Listings Count
              </label>
              <input
                type="number"
                min="1"
                value={settings.test_data_generation?.listings_count ?? 1}
                onChange={(e) =>
                  updateValue(
                    "test_data_generation",
                    "listings_count",
                    parseInt(e.target.value, 10)
                  )
                }
                className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex items-center space-x-3 mt-2">
              <input
                type="checkbox"
                checked={
                  settings.test_data_generation?.market_activity_enabled ||
                  false
                }
                onChange={() =>
                  toggle("test_data_generation", "market_activity_enabled")
                }
                className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
              />
              <div>
                <p className="text-sm font-medium text-gray-200">
                  Generate Market Activity
                </p>
                <p className="text-xs text-gray-400">
                  Simulate listing/bid traffic for load testing
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Feature Flags & A/B Testing */}
        <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold">Feature Flags & A/B Testing</h2>
              <p className="text-sm text-gray-400">
                Gate new features and manage experiment splits
              </p>
            </div>
            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={settings.feature_flags?.enabled || false}
                onChange={() => toggle("feature_flags", "enabled")}
                className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
              />
              <span className="text-sm text-gray-300">Feature Flags</span>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={settings.ab_testing?.enabled || false}
                onChange={() => toggle("ab_testing", "enabled")}
                className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
              />
              <div>
                <p className="text-sm font-medium text-gray-200">
                  Enable A/B Testing
                </p>
                <p className="text-xs text-gray-400">
                  Serve variant traffic based on split
                </p>
              </div>
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Split Percent
              </label>
              <input
                type="number"
                min="0"
                max="100"
                step="1"
                value={settings.ab_testing?.split_percent ?? 50}
                onChange={(e) =>
                  updateValue(
                    "ab_testing",
                    "split_percent",
                    parseFloat(e.target.value)
                  )
                }
                className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Variant ID
              </label>
              <input
                type="text"
                value={settings.ab_testing?.variant_id ?? ""}
                onChange={(e) =>
                  updateValue("ab_testing", "variant_id", e.target.value)
                }
                placeholder="e.g., variant-b"
                className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
        </section>

        {/* Debugging Tools */}
        <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold">Debugging Tools</h2>
              <p className="text-sm text-gray-400">
                Enable deep diagnostics for QA and ops
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="flex items-center space-x-3 bg-gray-700 rounded-lg p-4 border border-gray-600">
              <input
                type="checkbox"
                checked={settings.debug_tools?.session_inspect_enabled || false}
                onChange={() =>
                  toggle("debug_tools", "session_inspect_enabled")
                }
                className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
              />
              <div>
                <p className="text-sm font-medium text-gray-200">
                  Session Inspect
                </p>
                <p className="text-xs text-gray-400">
                  Inspect active sessions for debugging
                </p>
              </div>
            </label>

            <label className="flex items-center space-x-3 bg-gray-700 rounded-lg p-4 border border-gray-600">
              <input
                type="checkbox"
                checked={settings.debug_tools?.redis_inspect_enabled || false}
                onChange={() => toggle("debug_tools", "redis_inspect_enabled")}
                className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
              />
              <div>
                <p className="text-sm font-medium text-gray-200">
                  Redis Inspect
                </p>
                <p className="text-xs text-gray-400">
                  Expose Redis insights for ops debugging
                </p>
              </div>
            </label>

            <label className="flex items-center space-x-3 bg-gray-700 rounded-lg p-4 border border-gray-600">
              <input
                type="checkbox"
                checked={
                  settings.debug_tools?.websocket_connections_enabled || false
                }
                onChange={() =>
                  toggle("debug_tools", "websocket_connections_enabled")
                }
                className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
              />
              <div>
                <p className="text-sm font-medium text-gray-200">
                  WebSocket Connections
                </p>
                <p className="text-xs text-gray-400">
                  Monitor active WS connections
                </p>
              </div>
            </label>

            <label className="flex items-center space-x-3 bg-gray-700 rounded-lg p-4 border border-gray-600">
              <input
                type="checkbox"
                checked={settings.debug_tools?.verbose_logging_enabled || false}
                onChange={() =>
                  toggle("debug_tools", "verbose_logging_enabled")
                }
                className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
              />
              <div>
                <p className="text-sm font-medium text-gray-200">
                  Verbose Logging
                </p>
                <p className="text-xs text-gray-400">
                  Emit verbose logs for QA sessions
                </p>
              </div>
            </label>
          </div>
        </section>

        {/* Performance Testing */}
        <section className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold">Performance Testing</h2>
              <p className="text-sm text-gray-400">
                Configure perf test user load and target RPS
              </p>
            </div>
            <label className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={settings.performance_testing?.enabled || false}
                onChange={() => toggle("performance_testing", "enabled")}
                className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
              />
              <span className="text-sm text-gray-300">Enable</span>
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Concurrent Users
              </label>
              <input
                type="number"
                min="1"
                value={settings.performance_testing?.concurrent_users ?? 1}
                onChange={(e) =>
                  updateValue(
                    "performance_testing",
                    "concurrent_users",
                    parseInt(e.target.value, 10)
                  )
                }
                className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">
                Requests per Second
              </label>
              <input
                type="number"
                min="1"
                value={settings.performance_testing?.requests_per_second ?? 1}
                onChange={(e) =>
                  updateValue(
                    "performance_testing",
                    "requests_per_second",
                    parseInt(e.target.value, 10)
                  )
                }
                className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
        </section>

        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg font-semibold"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default AdminTestingDebugPage;
