/**
 * Admin Moderation Page
 * Chat moderation and user reports management
 */

import { useState, useEffect } from 'react';
import { adminAPI } from '../services/api';
import useAuthStore from '../stores/authStore';
import toast from 'react-hot-toast';

function AdminModerationPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState('chat');
  const [chatMessages, setChatMessages] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [filters, setFilters] = useState({
    search: '',
    status: '',
    resourceType: ''
  });

  useEffect(() => {
    if (user?.role !== 'admin') {
      toast.error('Admin access required');
      return;
    }
    loadData();
  }, [user, page, activeTab, filters.status, filters.resourceType]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'chat') {
        const res = await adminAPI.getChatMessages({
          page,
          search: filters.search
        });
        setChatMessages(res.data.data);
        setPagination(res.data.pagination);
      } else if (activeTab === 'reports') {
        const res = await adminAPI.getReports({
          page,
          status: filters.status,
          resource_type: filters.resourceType
        });
        setReports(res.data.data);
        setPagination(res.data.pagination);
      }
    } catch (error) {
      toast.error('Failed to load data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteMessage = async (messageId) => {
    const reason = prompt('Enter reason for deletion:');
    if (!reason) return;

    const confirmed = window.confirm('Are you sure you want to delete this message?');
    if (!confirmed) return;

    try {
      await adminAPI.deleteMessage(messageId, reason);
      toast.success('Message deleted successfully');
      loadData();
    } catch (error) {
      toast.error('Failed to delete message');
      console.error(error);
    }
  };

  const handleMuteUser = async (userId) => {
    const durationStr = prompt('Enter mute duration in minutes:');
    if (!durationStr) return;

    const duration = parseInt(durationStr);
    if (isNaN(duration) || duration <= 0) {
      toast.error('Invalid duration');
      return;
    }

    const reason = prompt('Enter reason for mute:');
    if (!reason) return;

    try {
      await adminAPI.muteUser(userId, { duration_minutes: duration }, reason);
      toast.success(`User muted for ${duration} minutes`);
    } catch (error) {
      toast.error('Failed to mute user');
      console.error(error);
    }
  };

  const handleResolveReport = async (reportId, action) => {
    const notes = prompt(`Enter resolution notes for ${action}:`);

    try {
      await adminAPI.resolveReport(reportId, { action, notes });
      toast.success(`Report ${action} successfully`);
      loadData();
    } catch (error) {
      toast.error(`Failed to ${action} report`);
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
          <h1 className="text-3xl font-bold mb-2">Content Moderation</h1>
          <p className="text-gray-400">Moderate chat messages and handle user reports</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {/* Tabs */}
        <div className="flex space-x-4 mb-6 border-b border-gray-700">
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === 'chat'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
            onClick={() => { setActiveTab('chat'); setPage(1); }}
          >
            Chat Messages
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === 'reports'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
            onClick={() => { setActiveTab('reports'); setPage(1); }}
          >
            User Reports
          </button>
        </div>

        {/* Filters */}
        <div className="bg-gray-800 rounded-lg p-4 mb-6">
          {activeTab === 'chat' && (
            <input
              type="text"
              placeholder="Search messages by content..."
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              onKeyDown={(e) => e.key === 'Enter' && loadData()}
              className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
            />
          )}

          {activeTab === 'reports' && (
            <div className="flex gap-4">
              <select
                value={filters.status}
                onChange={(e) => { setFilters({ ...filters, status: e.target.value }); setPage(1); }}
                className="flex-1 bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
              >
                <option value="">All Status</option>
                <option value="pending">Pending</option>
                <option value="resolved">Resolved</option>
                <option value="dismissed">Dismissed</option>
              </select>
              <select
                value={filters.resourceType}
                onChange={(e) => { setFilters({ ...filters, resourceType: e.target.value }); setPage(1); }}
                className="flex-1 bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
              >
                <option value="">All Types</option>
                <option value="user">User</option>
                <option value="land">Land</option>
                <option value="chat_message">Chat Message</option>
              </select>
            </div>
          )}
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : (
          <>
            {activeTab === 'chat' && (
              <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">User ID</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Message</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Time</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {chatMessages.map((msg) => (
                      <tr key={msg.message_id} className="hover:bg-gray-750">
                        <td className="px-6 py-4 text-sm text-gray-300 font-mono">{msg.sender_id.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm text-gray-300">{msg.content}</td>
                        <td className="px-6 py-4 text-sm text-gray-400">{new Date(msg.created_at).toLocaleString()}</td>
                        <td className="px-6 py-4 text-sm space-x-2">
                          <button
                            onClick={() => handleDeleteMessage(msg.message_id)}
                            className="text-red-400 hover:text-red-300 font-semibold"
                          >
                            Delete
                          </button>
                          <button
                            onClick={() => handleMuteUser(msg.sender_id)}
                            className="text-yellow-400 hover:text-yellow-300 font-semibold"
                          >
                            Mute User
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {chatMessages.length === 0 && (
                  <div className="text-center py-12 text-gray-400">
                    No messages found
                  </div>
                )}
              </div>
            )}

            {activeTab === 'reports' && (
              <div className="space-y-4">
                {reports.map((report) => (
                  <div key={report.report_id} className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          <span className={`px-3 py-1 rounded text-xs font-semibold ${
                            report.status === 'pending' ? 'bg-yellow-900 text-yellow-200' :
                            report.status === 'resolved' ? 'bg-green-900 text-green-200' :
                            'bg-gray-700 text-gray-300'
                          }`}>
                            {report.status}
                          </span>
                          <span className="text-sm text-gray-400 capitalize">{report.resource_type}</span>
                          <span className="text-sm text-gray-500">{new Date(report.created_at).toLocaleString()}</span>
                        </div>
                        <p className="text-gray-300 mb-2">
                          <span className="font-semibold">Reporter:</span> {report.reporter_id?.substring(0, 8)}...
                        </p>
                        {report.reported_user_id && (
                          <p className="text-gray-300 mb-2">
                            <span className="font-semibold">Reported User:</span> {report.reported_user_id.substring(0, 8)}...
                          </p>
                        )}
                        <p className="text-gray-300 mb-2">
                          <span className="font-semibold">Reason:</span> {report.reason}
                        </p>
                        {report.resolved_at && (
                          <p className="text-sm text-gray-500">
                            Resolved: {new Date(report.resolved_at).toLocaleString()}
                          </p>
                        )}
                      </div>
                      {report.status === 'pending' && (
                        <div className="flex space-x-2">
                          <button
                            onClick={() => handleResolveReport(report.report_id, 'resolved')}
                            className="bg-green-600 hover:bg-green-700 px-4 py-2 rounded font-semibold text-sm"
                          >
                            Resolve
                          </button>
                          <button
                            onClick={() => handleResolveReport(report.report_id, 'dismissed')}
                            className="bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded font-semibold text-sm"
                          >
                            Dismiss
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {reports.length === 0 && (
                  <div className="text-center py-12 text-gray-400 bg-gray-800 rounded-lg">
                    No reports found
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

export default AdminModerationPage;
