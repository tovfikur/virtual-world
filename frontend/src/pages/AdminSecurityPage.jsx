/**
 * Admin Security Page
 * View bans and security logs
 */

import { useState, useEffect } from 'react';
import { adminAPI } from '../services/api';
import useAuthStore from '../stores/authStore';
import toast from 'react-hot-toast';

function AdminSecurityPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState('bans');
  const [bans, setBans] = useState([]);
  const [securityLogs, setSecurityLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [filters, setFilters] = useState({
    activeOnly: true,
    banType: '',
    actionType: ''
  });

  useEffect(() => {
    if (user?.role !== 'admin') {
      toast.error('Admin access required');
      return;
    }
    loadData();
  }, [user, page, activeTab, filters.activeOnly, filters.banType, filters.actionType]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'bans') {
        const res = await adminAPI.getAllBans({
          page,
          active_only: filters.activeOnly,
          ban_type: filters.banType
        });
        setBans(res.data.data);
        setPagination(res.data.pagination);
      } else if (activeTab === 'logs') {
        const res = await adminAPI.getSecurityLogs({
          page,
          action_type: filters.actionType
        });
        setSecurityLogs(res.data.data);
        setPagination(res.data.pagination);
      }
    } catch (error) {
      toast.error('Failed to load data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleUnban = async (userId) => {
    if (!window.confirm('Are you sure you want to unban this user?')) return;

    try {
      await adminAPI.unbanUser(userId);
      toast.success('User unbanned successfully');
      loadData();
    } catch (error) {
      toast.error('Failed to unban user');
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
              activeTab === 'bans'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
            onClick={() => { setActiveTab('bans'); setPage(1); }}
          >
            Active Bans
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === 'logs'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
            onClick={() => { setActiveTab('logs'); setPage(1); }}
          >
            Security Logs
          </button>
        </div>

        {/* Filters */}
        <div className="bg-gray-800 rounded-lg p-4 mb-6">
          {activeTab === 'bans' && (
            <div className="flex gap-4">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={filters.activeOnly}
                  onChange={(e) => { setFilters({ ...filters, activeOnly: e.target.checked }); setPage(1); }}
                  className="w-5 h-5 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                />
                <span>Active Only</span>
              </label>
              <select
                value={filters.banType}
                onChange={(e) => { setFilters({ ...filters, banType: e.target.value }); setPage(1); }}
                className="flex-1 bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
              >
                <option value="">All Ban Types</option>
                <option value="full">Full Ban</option>
                <option value="marketplace">Marketplace Ban</option>
                <option value="chat">Chat Ban</option>
              </select>
            </div>
          )}

          {activeTab === 'logs' && (
            <select
              value={filters.actionType}
              onChange={(e) => { setFilters({ ...filters, actionType: e.target.value }); setPage(1); }}
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
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : (
          <>
            {activeTab === 'bans' && (
              <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">User ID</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Ban Type</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Reason</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Expires</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Created</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {bans.map((ban) => (
                      <tr key={ban.ban_id} className="hover:bg-gray-750">
                        <td className="px-6 py-4 text-sm text-gray-300 font-mono">{ban.user_id.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            ban.ban_type === 'full' ? 'bg-red-900 text-red-200' :
                            ban.ban_type === 'marketplace' ? 'bg-orange-900 text-orange-200' :
                            'bg-yellow-900 text-yellow-200'
                          }`}>
                            {ban.ban_type}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-300">{ban.reason}</td>
                        <td className="px-6 py-4 text-sm text-gray-400">
                          {ban.expires_at === 'permanent' ? 'Permanent' : new Date(ban.expires_at).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">{new Date(ban.created_at).toLocaleDateString()}</td>
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

            {activeTab === 'logs' && (
              <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Admin</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Action</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Resource</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Details</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {securityLogs.map((log) => (
                      <tr key={log.log_id} className="hover:bg-gray-750">
                        <td className="px-6 py-4 text-sm text-gray-300 font-mono">{log.user_id.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            log.action.includes('ban') || log.action.includes('suspend') ? 'bg-red-900 text-red-200' :
                            log.action.includes('delete') || log.action.includes('mute') ? 'bg-yellow-900 text-yellow-200' :
                            'bg-blue-900 text-blue-200'
                          }`}>
                            {log.action}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400 capitalize">{log.resource_type}</td>
                        <td className="px-6 py-4 text-sm text-gray-300 max-w-md truncate">{log.details}</td>
                        <td className="px-6 py-4 text-sm text-gray-400">{new Date(log.created_at).toLocaleString()}</td>
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

            {/* Pagination */}
            {pagination && pagination.pages > 1 && (
              <div className="flex items-center justify-between mt-6">
                <p className="text-sm text-gray-400">
                  Showing page {pagination.page} of {pagination.pages} ({pagination.total} total)
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
