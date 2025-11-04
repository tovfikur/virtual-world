/**
 * Admin Dashboard Page
 * Overview statistics and system monitoring
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../services/api';
import useAuthStore from '../stores/authStore';
import toast from 'react-hot-toast';

function AdminDashboardPage() {
  const { user } = useAuthStore();
  const [stats, setStats] = useState(null);
  const [revenueData, setRevenueData] = useState(null);
  const [systemHealth, setSystemHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user?.role !== 'admin') {
      toast.error('Admin access required');
      return;
    }
    loadDashboardData();
  }, [user]);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [statsRes, revenueRes, healthRes] = await Promise.all([
        adminAPI.getDashboardStats(),
        adminAPI.getRevenueAnalytics(30),
        adminAPI.getSystemHealth()
      ]);

      setStats(statsRes.data);
      setRevenueData(revenueRes.data);
      setSystemHealth(healthRes.data);
    } catch (error) {
      toast.error('Failed to load dashboard data');
      console.error(error);
    } finally {
      setLoading(false);
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
          <h1 className="text-3xl font-bold mb-2">Admin Dashboard</h1>
          <p className="text-gray-400">Platform overview and management</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {/* Quick Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {/* Users */}
          <div className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Users</h3>
              <svg className="w-8 h-8 opacity-75" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            </div>
            <p className="text-3xl font-bold">{stats?.total_users || 0}</p>
            <p className="text-sm opacity-75 mt-2">
              {stats?.active_users_today || 0} active today
            </p>
          </div>

          {/* Lands */}
          <div className="bg-gradient-to-br from-green-600 to-green-800 rounded-lg p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Lands</h3>
              <svg className="w-8 h-8 opacity-75" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
            </div>
            <p className="text-3xl font-bold">{stats?.owned_lands || 0}</p>
            <p className="text-sm opacity-75 mt-2">
              of {stats?.total_lands || 0} total
            </p>
          </div>

          {/* Listings */}
          <div className="bg-gradient-to-br from-purple-600 to-purple-800 rounded-lg p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Listings</h3>
              <svg className="w-8 h-8 opacity-75" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <p className="text-3xl font-bold">{stats?.active_listings || 0}</p>
            <p className="text-sm opacity-75 mt-2">
              of {stats?.total_listings || 0} total
            </p>
          </div>

          {/* Revenue */}
          <div className="bg-gradient-to-br from-yellow-600 to-yellow-800 rounded-lg p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Revenue</h3>
              <svg className="w-8 h-8 opacity-75" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-3xl font-bold">{stats?.total_revenue_bdt?.toLocaleString() || 0} BDT</p>
            <p className="text-sm opacity-75 mt-2">
              {stats?.transactions_today || 0} transactions today
            </p>
          </div>
        </div>

        {/* System Health */}
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-8">
          <h2 className="text-xl font-bold mb-4">System Health</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="flex items-center space-x-4">
              <div className={`w-3 h-3 rounded-full ${systemHealth?.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'} animate-pulse`}></div>
              <div>
                <p className="text-sm text-gray-400">Overall Status</p>
                <p className="font-semibold capitalize">{systemHealth?.status || 'Unknown'}</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <div className={`w-3 h-3 rounded-full ${systemHealth?.components?.database === 'healthy' ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <div>
                <p className="text-sm text-gray-400">Database</p>
                <p className="font-semibold capitalize">{systemHealth?.components?.database || 'Unknown'}</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <div className={`w-3 h-3 rounded-full ${systemHealth?.components?.redis === 'healthy' ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <div>
                <p className="text-sm text-gray-400">Redis Cache</p>
                <p className="font-semibold capitalize">{systemHealth?.components?.redis || 'Unknown'}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Revenue Chart (Simplified) */}
        {revenueData && (
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-8">
            <h2 className="text-xl font-bold mb-4">Revenue (Last 30 Days)</h2>
            <div className="flex items-end space-x-2 h-48">
              {revenueData.daily_data?.slice(-14).map((day, idx) => {
                const maxRevenue = Math.max(...revenueData.daily_data.map(d => d.revenue));
                const height = (day.revenue / maxRevenue) * 100;
                return (
                  <div key={idx} className="flex-1 flex flex-col items-center">
                    <div
                      className="w-full bg-blue-600 rounded-t hover:bg-blue-500 transition-colors cursor-pointer"
                      style={{ height: `${height}%` }}
                      title={`${day.date}: ${day.revenue} BDT`}
                    ></div>
                    <span className="text-xs text-gray-500 mt-2">{new Date(day.date).getDate()}</span>
                  </div>
                );
              })}
            </div>
            <div className="mt-4 text-center">
              <p className="text-2xl font-bold text-green-400">
                {revenueData.total_revenue?.toLocaleString()} BDT
              </p>
              <p className="text-sm text-gray-400">Total Revenue (30 days)</p>
            </div>
          </div>
        )}

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Link
            to="/admin/users"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-6 border border-gray-700 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold">User Management</h3>
              <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
              </svg>
            </div>
            <p className="text-sm text-gray-400">Manage users, roles, and balances</p>
          </Link>

          <Link
            to="/admin/marketplace"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-6 border border-gray-700 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold">Marketplace</h3>
              <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <p className="text-sm text-gray-400">Moderate listings and transactions</p>
          </Link>

          <Link
            to="/admin/lands"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-6 border border-gray-700 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold">Land Management</h3>
              <svg className="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
            </div>
            <p className="text-sm text-gray-400">View analytics and manage ownership</p>
          </Link>

          <Link
            to="/admin/economy"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-6 border border-gray-700 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold">Economy Settings</h3>
              <svg className="w-6 h-6 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-sm text-gray-400">Configure pricing and fees</p>
          </Link>

          <Link
            to="/admin/config"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-6 border border-gray-700 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold">World Configuration</h3>
              <svg className="w-6 h-6 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <p className="text-sm text-gray-400">Configure world settings and features</p>
          </Link>

          <Link
            to="/admin/logs"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-6 border border-gray-700 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold">Audit Logs</h3>
              <svg className="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-sm text-gray-400">View system audit trail and activity</p>
          </Link>

          <Link
            to="/admin/moderation"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-6 border border-gray-700 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold">Moderation</h3>
              <svg className="w-6 h-6 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <p className="text-sm text-gray-400">Moderate chat and handle reports</p>
          </Link>

          <Link
            to="/admin/features"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-6 border border-gray-700 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold">Features & Limits</h3>
              <svg className="w-6 h-6 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
            </div>
            <p className="text-sm text-gray-400">Toggle features and set limits</p>
          </Link>

          <Link
            to="/admin/communication"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-6 border border-gray-700 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold">Communication</h3>
              <svg className="w-6 h-6 text-pink-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z" />
              </svg>
            </div>
            <p className="text-sm text-gray-400">Announcements and broadcasts</p>
          </Link>

          <Link
            to="/admin/security"
            className="bg-gray-800 hover:bg-gray-700 rounded-lg p-6 border border-gray-700 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold">Security</h3>
              <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <p className="text-sm text-gray-400">Monitor bans and security logs</p>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default AdminDashboardPage;
