/**
 * Admin Audit Logs Page
 * View system audit trail and activity logs
 */

import { useState, useEffect } from "react";
import { adminAPI } from "../services/api";
import useAuthStore from "../stores/authStore";
import toast from "react-hot-toast";

function AdminLogsPage() {
  const { user } = useAuthStore();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [actionFilter, setActionFilter] = useState("");
  const [userIdFilter, setUserIdFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [logLevel, setLogLevel] = useState("INFO");
  const [savingLogLevel, setSavingLogLevel] = useState(false);
  const [cachePrefix, setCachePrefix] = useState("");

  useEffect(() => {
    if (user?.role === "admin") {
      loadLogs();
      loadLogLevel();
    }
  }, [user, page, actionFilter, userIdFilter]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const params = { page, limit: 50 };
      if (actionFilter) params.action = actionFilter;
      if (userIdFilter) params.user_id = userIdFilter;
      if (dateFrom) params.start_date = dateFrom;
      if (dateTo) params.end_date = dateTo;

      const response = await adminAPI.getAuditLogs(params);
      setLogs(response.data.data);
      setTotal(response.data.pagination.total);
    } catch (error) {
      toast.error("Failed to load audit logs");
    } finally {
      setLoading(false);
    }
  };

  const loadLogLevel = async () => {
    try {
      const res = await adminAPI.getLogLevel();
      if (res.data?.level) setLogLevel(res.data.level);
    } catch (e) {
      // ignore
    }
  };

  const handleSaveLogLevel = async () => {
    setSavingLogLevel(true);
    try {
      await adminAPI.setLogLevel(logLevel);
      toast.success("Log level updated");
    } catch (e) {
      toast.error("Failed to update log level");
    } finally {
      setSavingLogLevel(false);
    }
  };

  const handleClearCacheAll = async () => {
    if (!window.confirm("Clear entire cache? This cannot be undone.")) return;
    try {
      await adminAPI.clearCacheAll();
      toast.success("Cache cleared");
    } catch (e) {
      toast.error("Failed to clear cache");
    }
  };

  const handleClearCachePrefix = async () => {
    if (!cachePrefix.trim()) {
      toast.error("Enter a prefix");
      return;
    }
    try {
      await adminAPI.clearCacheByPrefix(cachePrefix.trim());
      toast.success("Cache cleared for prefix");
    } catch (e) {
      toast.error("Failed to clear cache by prefix");
    }
  };

  const totalPages = Math.ceil(total / 50);

  const exportCsv = (rows, headers, filename) => {
    if (!rows?.length) {
      toast.error("No data to export");
      return;
    }
    const headerLine = headers.map((h) => h.label).join(",");
    const lines = rows.map((row) =>
      headers
        .map((h) => {
          const val = row[h.key];
          return JSON.stringify(val ?? "");
        })
        .join(",")
    );
    const csv = [headerLine, ...lines].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  const getActionColor = (action) => {
    switch (action) {
      case "login":
      case "register":
        return "bg-blue-600";
      case "update_user":
      case "update_world_config":
        return "bg-yellow-600";
      case "delete":
        return "bg-red-600";
      case "purchase":
      case "bid":
        return "bg-green-600";
      default:
        return "bg-gray-600";
    }
  };

  if (user?.role !== "admin") {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-400 mb-4">
            Access Denied
          </h1>
          <p className="text-gray-400">Admin access required</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-2">Audit Logs</h1>
          <p className="text-gray-400">System activity and audit trail</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {/* Log Level & Cache Tools */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h2 className="text-xl font-bold mb-4">Log Level</h2>
            <div className="flex items-center gap-4">
              <select
                value={logLevel}
                onChange={(e) => setLogLevel(e.target.value)}
                className="px-4 py-2 bg-gray-700 text-white rounded border border-gray-600 focus:border-blue-500"
              >
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
              </select>
              <button
                onClick={handleSaveLogLevel}
                disabled={savingLogLevel}
                className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded font-semibold disabled:bg-gray-600"
              >
                {savingLogLevel ? "Saving..." : "Save"}
              </button>
            </div>
          </div>

          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h2 className="text-xl font-bold mb-4">Cache Management</h2>
            <div className="space-y-4">
              <button
                onClick={handleClearCacheAll}
                className="bg-red-600 hover:bg-red-700 px-6 py-2 rounded font-semibold"
              >
                Clear All Cache
              </button>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Prefix (e.g., chunks:)"
                  value={cachePrefix}
                  onChange={(e) => setCachePrefix(e.target.value)}
                  className="flex-1 px-4 py-2 bg-gray-700 text-white rounded border border-gray-600 focus:border-blue-500"
                />
                <button
                  onClick={handleClearCachePrefix}
                  className="bg-yellow-600 hover:bg-yellow-700 px-6 py-2 rounded font-semibold"
                >
                  Clear by Prefix
                </button>
              </div>
            </div>
          </div>
        </div>
        {/* Filters */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <input
              type="text"
              placeholder="Filter by User ID..."
              value={userIdFilter}
              onChange={(e) => setUserIdFilter(e.target.value)}
              className="px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
            />
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
            >
              <option value="">All Actions</option>
              <option value="login">Login</option>
              <option value="register">Register</option>
              <option value="purchase">Purchase</option>
              <option value="bid">Bid</option>
              <option value="update_user">Update User</option>
              <option value="update_world_config">Update Config</option>
            </select>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
            />
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
            />
            <button
              onClick={loadLogs}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors font-semibold"
            >
              Refresh
            </button>
          </div>
          <div className="mt-4">
            <button
              onClick={() =>
                exportCsv(
                  logs,
                  [
                    { key: "created_at", label: "timestamp" },
                    { key: "user_id", label: "user_id" },
                    { key: "action", label: "action" },
                    { key: "resource_type", label: "resource_type" },
                    { key: "resource_id", label: "resource_id" },
                    { key: "details", label: "details" },
                    { key: "ip_address", label: "ip_address" },
                  ],
                  `audit-logs-page-${page}.csv`
                )
              }
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg font-semibold"
            >
              Export Current View (CSV)
            </button>
          </div>
        </div>

        {/* Logs List */}
        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : logs.length === 0 ? (
          <div className="text-center py-12 bg-gray-800 rounded-lg border border-gray-700">
            <p className="text-gray-400 text-lg">No audit logs found</p>
          </div>
        ) : (
          <>
            <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                        Timestamp
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                        User ID
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                        Action
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                        Resource
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                        Details
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                        IP Address
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {logs.map((log) => (
                      <tr
                        key={log.log_id}
                        className="hover:bg-gray-700 transition-colors"
                      >
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">
                          {new Date(log.created_at).toLocaleString()}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-300">
                          {log.user_id
                            ? log.user_id.substring(0, 8) + "..."
                            : "N/A"}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span
                            className={`px-2 py-1 rounded text-xs font-semibold ${getActionColor(
                              log.action
                            )}`}
                          >
                            {log.action}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <div>
                            <span className="text-gray-400">
                              {log.resource_type || "N/A"}
                            </span>
                            {log.resource_id && (
                              <span className="block text-xs text-gray-500 font-mono">
                                {log.resource_id.substring(0, 8)}...
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-300 max-w-md truncate">
                          {log.details || "No details"}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400 font-mono">
                          {log.ip_address || "N/A"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Pagination */}
            <div className="mt-6 flex justify-center items-center space-x-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                Previous
              </button>
              <span className="text-gray-400">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                Next
              </button>
            </div>

            {/* Stats */}
            <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <p className="text-sm text-gray-400">Total Logs</p>
                <p className="text-2xl font-bold">{total.toLocaleString()}</p>
              </div>
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <p className="text-sm text-gray-400">Showing</p>
                <p className="text-2xl font-bold">{logs.length}</p>
              </div>
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <p className="text-sm text-gray-400">Current Page</p>
                <p className="text-2xl font-bold">
                  {page} / {totalPages}
                </p>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default AdminLogsPage;
