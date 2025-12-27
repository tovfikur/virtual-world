/**
 * Admin Security Page
 * View bans and security logs
 */

import { useState, useEffect } from "react";
import { adminAPI } from "../services/api";
import useAuthStore from "../stores/authStore";
import toast from "react-hot-toast";

function AdminSecurityPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState("bans");
  const [bans, setBans] = useState([]);
  const [securityLogs, setSecurityLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [filters, setFilters] = useState({
    activeOnly: true,
    banType: "",
    actionType: "",
  });
  const [authSettings, setAuthSettings] = useState({
    access_token_minutes: 60,
    refresh_token_days: 7,
    password_min_length: 8,
    password_require_uppercase: true,
    password_require_number: true,
    password_require_special: true,
    login_max_attempts: 5,
    login_lockout_minutes: 15,
    max_sessions_per_user: 3,
  });
  const [savingAuth, setSavingAuth] = useState(false);
  const [ipBlocks, setIpBlocks] = useState([]);
  const [ipWhitelist, setIpWhitelist] = useState([]);
  const [ipPage, setIpPage] = useState(1);
  const [ipFilters, setIpFilters] = useState({ search: "" });
  const [ipForm, setIpForm] = useState({
    ip: "",
    reason: "",
    expiresMinutes: "",
  });
  const [whitelistForm, setWhitelistForm] = useState({ ip: "", note: "" });

  useEffect(() => {
    if (user?.role !== "admin") {
      toast.error("Admin access required");
      return;
    }
    loadData();
  }, [
    user,
    page,
    activeTab,
    filters.activeOnly,
    filters.banType,
    filters.actionType,
    ipPage,
    ipFilters.search,
  ]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === "bans") {
        const res = await adminAPI.getAllBans({
          page,
          active_only: filters.activeOnly,
          ban_type: filters.banType,
        });
        setBans(res.data.data);
        setPagination(res.data.pagination);
      } else if (activeTab === "logs") {
        const res = await adminAPI.getSecurityLogs({
          page,
          action_type: filters.actionType,
        });
        setSecurityLogs(res.data.data);
        setPagination(res.data.pagination);
      } else if (activeTab === "auth") {
        const res = await adminAPI.getSystemLimits();
        setAuthSettings((prev) => ({ ...prev, ...(res.data || {}) }));
      } else if (activeTab === "ip") {
        const [blocksRes, wlRes] = await Promise.all([
          adminAPI.getIpBlocks({ page: ipPage, search: ipFilters.search }),
          adminAPI.getIpWhitelist({ page: ipPage, search: ipFilters.search }),
        ]);
        setIpBlocks(blocksRes.data?.data || []);
        setIpWhitelist(wlRes.data?.data || []);
      }
    } catch (error) {
      toast.error("Failed to load data");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddIpBlock = async (e) => {
    e.preventDefault();
    if (!ipForm.ip || !ipForm.reason) {
      toast.error("IP and reason are required");
      return;
    }
    try {
      await adminAPI.addIpBlock(
        ipForm.ip,
        ipForm.reason,
        ipForm.expiresMinutes ? parseInt(ipForm.expiresMinutes) : null
      );
      toast.success("IP block added");
      setIpForm({ ip: "", reason: "", expiresMinutes: "" });
      loadData();
    } catch (error) {
      toast.error("Failed to add IP block");
    }
  };

  const handleRemoveIpBlock = async (blockId) => {
    if (!window.confirm("Remove IP block?")) return;
    try {
      await adminAPI.removeIpBlock(blockId);
      toast.success("IP block removed");
      loadData();
    } catch (error) {
      toast.error("Failed to remove IP block");
    }
  };

  const handleAddWhitelist = async (e) => {
    e.preventDefault();
    if (!whitelistForm.ip) {
      toast.error("IP is required");
      return;
    }
    try {
      await adminAPI.addIpWhitelist(whitelistForm.ip, whitelistForm.note);
      toast.success("IP whitelisted");
      setWhitelistForm({ ip: "", note: "" });
      loadData();
    } catch (error) {
      toast.error("Failed to add whitelist entry");
    }
  };

  const handleRemoveWhitelist = async (entryId) => {
    if (!window.confirm("Remove whitelist entry?")) return;
    try {
      await adminAPI.removeIpWhitelist(entryId);
      toast.success("Whitelist entry removed");
      loadData();
    } catch (error) {
      toast.error("Failed to remove whitelist entry");
    }
  };

  const handleSaveAuth = async () => {
    // Basic client-side guardrails
    if (
      authSettings.access_token_minutes < 5 ||
      authSettings.refresh_token_days < 1 ||
      authSettings.password_min_length < 6 ||
      authSettings.login_max_attempts < 1 ||
      authSettings.login_lockout_minutes < 1 ||
      authSettings.max_sessions_per_user < 1
    ) {
      toast.error("Please verify configuration bounds");
      return;
    }

    setSavingAuth(true);
    try {
      await adminAPI.updateSystemLimits(authSettings);
      toast.success("Auth & session settings updated");
    } catch (error) {
      toast.error("Failed to update settings");
      console.error(error);
    } finally {
      setSavingAuth(false);
    }
  };

  const handleUnban = async (userId) => {
    if (!window.confirm("Are you sure you want to unban this user?")) return;

    try {
      await adminAPI.unbanUser(userId);
      toast.success("User unbanned successfully");
      loadData();
    } catch (error) {
      toast.error("Failed to unban user");
      console.error(error);
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

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-2">Security Dashboard</h1>
          <p className="text-gray-400">Monitor bans and security events</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {/* Tabs */}
        <div className="flex space-x-4 mb-6 border-b border-gray-700">
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "bans"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => {
              setActiveTab("bans");
              setPage(1);
            }}
          >
            Active Bans
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "logs"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => {
              setActiveTab("logs");
              setPage(1);
            }}
          >
            Security Logs
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "auth"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => {
              setActiveTab("auth");
              setPage(1);
            }}
          >
            Auth & Sessions
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "ip"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => {
              setActiveTab("ip");
              setIpPage(1);
            }}
          >
            IP Controls
          </button>
        </div>

        {/* Filters / Subheader */}
        <div className="bg-gray-800 rounded-lg p-4 mb-6">
          {activeTab === "bans" && (
            <div className="flex gap-4">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={filters.activeOnly}
                  onChange={(e) => {
                    setFilters({ ...filters, activeOnly: e.target.checked });
                    setPage(1);
                  }}
                  className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <span>Active Only</span>
              </label>
              <select
                value={filters.banType}
                onChange={(e) => {
                  setFilters({ ...filters, banType: e.target.value });
                  setPage(1);
                }}
                className="flex-1 bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
              >
                <option value="">All Ban Types</option>
                <option value="full">Full Ban</option>
                <option value="marketplace">Marketplace Ban</option>
                <option value="chat">Chat Ban</option>
              </select>
            </div>
          )}

          {activeTab === "ip" && (
            <div className="space-y-4">
              <div className="flex flex-col md:flex-row md:items-center gap-3">
                <input
                  type="text"
                  placeholder="Search IP or note"
                  value={ipFilters.search}
                  onChange={(e) => {
                    setIpFilters({ ...ipFilters, search: e.target.value });
                    setIpPage(1);
                  }}
                  className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 w-full md:w-80"
                />
                <span className="text-xs text-gray-400">
                  Includes blocked and whitelisted results
                </span>
                <button
                  className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded font-semibold"
                  onClick={() => loadData()}
                >
                  Refresh
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* IP Blocks */}
                <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                  <h3 className="text-xl font-bold mb-4">Blocked IPs</h3>
                  <form onSubmit={handleAddIpBlock} className="space-y-3 mb-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <input
                        type="text"
                        placeholder="IP address"
                        value={ipForm.ip}
                        onChange={(e) =>
                          setIpForm({ ...ipForm, ip: e.target.value })
                        }
                        className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
                      />
                      <input
                        type="text"
                        placeholder="Reason"
                        value={ipForm.reason}
                        onChange={(e) =>
                          setIpForm({ ...ipForm, reason: e.target.value })
                        }
                        className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
                      />
                      <input
                        type="number"
                        placeholder="Expires (min, optional)"
                        value={ipForm.expiresMinutes}
                        onChange={(e) =>
                          setIpForm({
                            ...ipForm,
                            expiresMinutes: e.target.value,
                          })
                        }
                        className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
                      />
                    </div>
                    <button
                      type="submit"
                      className="bg-red-600 hover:bg-red-700 px-6 py-2 rounded font-semibold"
                    >
                      Add Block
                    </button>
                  </form>
                  <div className="space-y-2">
                    {ipBlocks.map((b) => (
                      <div
                        key={b.block_id}
                        className="flex items-center justify-between bg-gray-700 rounded p-3"
                      >
                        <div>
                          <p className="font-mono text-sm">{b.ip_address}</p>
                          <p className="text-xs text-gray-400">
                            {b.reason}{" "}
                            {b.expires_at &&
                              `(expires ${new Date(
                                b.expires_at
                              ).toLocaleString()})`}
                          </p>
                        </div>
                        <button
                          onClick={() => handleRemoveIpBlock(b.block_id)}
                          className="text-red-400 hover:text-red-300 font-semibold"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                    {ipBlocks.length === 0 && (
                      <p className="text-gray-400">No blocked IPs</p>
                    )}
                  </div>
                </div>

                {/* IP Whitelist */}
                <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                  <h3 className="text-xl font-bold mb-4">Whitelisted IPs</h3>
                  <form
                    onSubmit={handleAddWhitelist}
                    className="space-y-3 mb-4"
                  >
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <input
                        type="text"
                        placeholder="IP address"
                        value={whitelistForm.ip}
                        onChange={(e) =>
                          setWhitelistForm({
                            ...whitelistForm,
                            ip: e.target.value,
                          })
                        }
                        className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
                      />
                      <input
                        type="text"
                        placeholder="Note (optional)"
                        value={whitelistForm.note}
                        onChange={(e) =>
                          setWhitelistForm({
                            ...whitelistForm,
                            note: e.target.value,
                          })
                        }
                        className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
                      />
                      <button
                        type="submit"
                        className="bg-green-600 hover:bg-green-700 px-6 py-2 rounded font-semibold"
                      >
                        Add Whitelist
                      </button>
                    </div>
                  </form>
                  <div className="space-y-2">
                    {ipWhitelist.map((w) => (
                      <div
                        key={w.entry_id}
                        className="flex items-center justify-between bg-gray-700 rounded p-3"
                      >
                        <div>
                          <p className="font-mono text-sm">{w.ip_address}</p>
                          {w.note && (
                            <p className="text-xs text-gray-400">{w.note}</p>
                          )}
                        </div>
                        <button
                          onClick={() => handleRemoveWhitelist(w.entry_id)}
                          className="text-yellow-400 hover:text-yellow-300 font-semibold"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                    {ipWhitelist.length === 0 && (
                      <p className="text-gray-400">No whitelisted IPs</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between bg-gray-800 rounded-lg p-4 border border-gray-700">
                <span className="text-gray-300 text-sm">Page {ipPage}</span>
                <div className="flex gap-3">
                  <button
                    type="button"
                    className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded font-semibold disabled:opacity-50"
                    disabled={ipPage <= 1}
                    onClick={() => setIpPage((p) => Math.max(1, p - 1))}
                  >
                    Prev
                  </button>
                  <button
                    type="button"
                    className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded font-semibold disabled:opacity-50"
                    disabled={ipBlocks.length === 0 && ipWhitelist.length === 0}
                    onClick={() => setIpPage((p) => p + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === "logs" && (
            <select
              value={filters.actionType}
              onChange={(e) => {
                setFilters({ ...filters, actionType: e.target.value });
                setPage(1);
              }}
              className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
            >
              <option value="">All Actions</option>
              <option value="ban_user">Ban User</option>
              <option value="unban_user">Unban User</option>
              <option value="suspend_user">Suspend User</option>
              <option value="unsuspend_user">Unsuspend User</option>
              <option value="delete_message">Delete Message</option>
              <option value="mute_user">Mute User</option>
              <option value="resolve_report">Resolve Report</option>
            </select>
          )}

          {activeTab === "auth" && (
            <p className="text-gray-400">
              Configure token lifetimes, password policy, login limits, and
              session caps
            </p>
          )}
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : (
          <>
            {activeTab === "bans" && (
              <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        User ID
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Ban Type
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Reason
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Expires
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Created
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {bans.map((ban) => (
                      <tr key={ban.ban_id} className="hover:bg-gray-750">
                        <td className="px-6 py-4 text-sm text-gray-300 font-mono">
                          {ban.user_id.substring(0, 8)}...
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <span
                            className={`px-2 py-1 rounded text-xs font-semibold ${
                              ban.ban_type === "full"
                                ? "bg-red-900 text-red-200"
                                : ban.ban_type === "marketplace"
                                ? "bg-orange-900 text-orange-200"
                                : "bg-yellow-900 text-yellow-200"
                            }`}
                          >
                            {ban.ban_type}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-300">
                          {ban.reason}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">
                          {ban.expires_at === "permanent"
                            ? "Permanent"
                            : new Date(ban.expires_at).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">
                          {new Date(ban.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          {ban.is_active && (
                            <button
                              onClick={() => handleUnban(ban.user_id)}
                              className="text-green-400 hover:text-green-300 font-semibold"
                            >
                              Unban
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {bans.length === 0 && (
                  <div className="text-center py-12 text-gray-400">
                    No bans found
                  </div>
                )}
              </div>
            )}

            {activeTab === "logs" && (
              <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Admin
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Action
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Resource
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Details
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Time
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {securityLogs.map((log) => (
                      <tr key={log.log_id} className="hover:bg-gray-750">
                        <td className="px-6 py-4 text-sm text-gray-300 font-mono">
                          {log.user_id.substring(0, 8)}...
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <span
                            className={`px-2 py-1 rounded text-xs font-semibold ${
                              log.action.includes("ban") ||
                              log.action.includes("suspend")
                                ? "bg-red-900 text-red-200"
                                : log.action.includes("delete") ||
                                  log.action.includes("mute")
                                ? "bg-yellow-900 text-yellow-200"
                                : "bg-blue-900 text-blue-200"
                            }`}
                          >
                            {log.action}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400 capitalize">
                          {log.resource_type}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-300 max-w-md truncate">
                          {log.details}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">
                          {new Date(log.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {securityLogs.length === 0 && (
                  <div className="text-center py-12 text-gray-400">
                    No security logs found
                  </div>
                )}
              </div>
            )}

            {activeTab === "auth" && (
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-xl font-bold mb-4">
                  Auth & Session Settings
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Access Token Lifetime (minutes)
                    </label>
                    <input
                      type="number"
                      value={authSettings.access_token_minutes}
                      onChange={(e) =>
                        setAuthSettings({
                          ...authSettings,
                          access_token_minutes: parseInt(e.target.value || "0"),
                        })
                      }
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Refresh Token Lifetime (days)
                    </label>
                    <input
                      type="number"
                      value={authSettings.refresh_token_days}
                      onChange={(e) =>
                        setAuthSettings({
                          ...authSettings,
                          refresh_token_days: parseInt(e.target.value || "0"),
                        })
                      }
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Password Min Length
                    </label>
                    <input
                      type="number"
                      value={authSettings.password_min_length}
                      onChange={(e) =>
                        setAuthSettings({
                          ...authSettings,
                          password_min_length: parseInt(e.target.value || "0"),
                        })
                      }
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-300">
                      Password Requirements
                    </label>
                    <div className="flex items-center gap-4">
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={authSettings.password_require_uppercase}
                          onChange={(e) =>
                            setAuthSettings({
                              ...authSettings,
                              password_require_uppercase: e.target.checked,
                            })
                          }
                        />
                        <span>Uppercase</span>
                      </label>
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={authSettings.password_require_number}
                          onChange={(e) =>
                            setAuthSettings({
                              ...authSettings,
                              password_require_number: e.target.checked,
                            })
                          }
                        />
                        <span>Number</span>
                      </label>
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={authSettings.password_require_special}
                          onChange={(e) =>
                            setAuthSettings({
                              ...authSettings,
                              password_require_special: e.target.checked,
                            })
                          }
                        />
                        <span>Special</span>
                      </label>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Login Max Attempts
                    </label>
                    <input
                      type="number"
                      value={authSettings.login_max_attempts}
                      onChange={(e) =>
                        setAuthSettings({
                          ...authSettings,
                          login_max_attempts: parseInt(e.target.value || "0"),
                        })
                      }
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Lockout Duration (minutes)
                    </label>
                    <input
                      type="number"
                      value={authSettings.login_lockout_minutes}
                      onChange={(e) =>
                        setAuthSettings({
                          ...authSettings,
                          login_lockout_minutes: parseInt(
                            e.target.value || "0"
                          ),
                        })
                      }
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Max Sessions Per User
                    </label>
                    <input
                      type="number"
                      value={authSettings.max_sessions_per_user}
                      onChange={(e) =>
                        setAuthSettings({
                          ...authSettings,
                          max_sessions_per_user: parseInt(
                            e.target.value || "0"
                          ),
                        })
                      }
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-6 border-t border-gray-700 mt-6">
                  <button
                    onClick={handleSaveAuth}
                    disabled={savingAuth}
                    className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-8 py-3 rounded font-semibold transition-colors"
                  >
                    {savingAuth ? "Saving..." : "Save Settings"}
                  </button>
                </div>

                <div className="mt-8 bg-gray-700 rounded p-4 border border-gray-600">
                  <h4 className="font-semibold mb-2">
                    IP Blocking / Whitelist
                  </h4>
                  <p className="text-sm text-gray-300">
                    UI for IP block/whitelist is coming here. Backend endpoints
                    exist; this panel will be wired next.
                  </p>
                </div>
              </div>
            )}

            {/* Pagination */}
            {pagination && pagination.pages > 1 && (
              <div className="flex items-center justify-between mt-6">
                <p className="text-sm text-gray-400">
                  Showing page {pagination.page} of {pagination.pages} (
                  {pagination.total} total)
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(page - 1)}
                    disabled={page === 1}
                    className="px-4 py-2 bg-gray-700 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-600"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(page + 1)}
                    disabled={page === pagination.pages}
                    className="px-4 py-2 bg-gray-700 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-600"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default AdminSecurityPage;
