/**
 * Admin Marketplace Management Page
 * View and moderate marketplace listings and transactions
 */

import { useState, useEffect } from 'react';
import { adminAPI } from '../services/api';
import useAuthStore from '../stores/authStore';
import toast from 'react-hot-toast';

function AdminMarketplacePage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState('listings');
  const [listings, setListings] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (user?.role !== 'admin') {
      toast.error('Admin access required');
      return;
    }
    loadData();
  }, [user, page, statusFilter, activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'listings') {
        const res = await adminAPI.getMarketplaceListings({
          page,
          status: statusFilter,
          search: searchQuery
        });
        setListings(res.data.data);
        setPagination(res.data.pagination);
      } else if (activeTab === 'transactions') {
        const res = await adminAPI.getTransactions({
          page,
          status: statusFilter,
          search: searchQuery
        });
        setTransactions(res.data.data);
        setPagination(res.data.pagination);
      }
    } catch (error) {
      toast.error('Failed to load data');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveListing = async (listingId) => {
    const reason = prompt('Enter reason for removal:');
    if (!reason) return;

    try {
      await adminAPI.removeListing(listingId, reason);
      toast.success('Listing removed successfully');
      loadData();
    } catch (error) {
      toast.error('Failed to remove listing');
      console.error(error);
    }
  };

  const handleRefundTransaction = async (transactionId) => {
    const reason = prompt('Enter reason for refund:');
    if (!reason) return;

    const confirmed = window.confirm('Are you sure you want to refund this transaction? This action cannot be undone.');
    if (!confirmed) return;

    try {
      await adminAPI.refundTransaction(transactionId, reason);
      toast.success('Transaction refunded successfully');
      loadData();
    } catch (error) {
      toast.error('Failed to refund transaction');
      console.error(error);
    }
  };

  const handleExportTransactions = async () => {
    try {
      const res = await adminAPI.exportTransactions();
      // Convert to CSV and download
      const csvContent = convertToCSV(res.data.data);
      downloadCSV(csvContent, 'transactions.csv');
      toast.success('Transactions exported successfully');
    } catch (error) {
      toast.error('Failed to export transactions');
      console.error(error);
    }
  };

  const convertToCSV = (data) => {
    if (!data || data.length === 0) return '';

    const headers = Object.keys(data[0]).join(',');
    const rows = data.map(row => Object.values(row).join(',')).join('\n');
    return `${headers}\n${rows}`;
  };

  const downloadCSV = (content, filename) => {
    const blob = new Blob([content], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
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
          <h1 className="text-3xl font-bold mb-2">Marketplace Management</h1>
          <p className="text-gray-400">Moderate listings and manage transactions</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {/* Tabs */}
        <div className="flex space-x-4 mb-6 border-b border-gray-700">
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === 'listings'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
            onClick={() => { setActiveTab('listings'); setPage(1); }}
          >
            Listings
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === 'transactions'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
            onClick={() => { setActiveTab('transactions'); setPage(1); }}
          >
            Transactions
          </button>
        </div>

        {/* Filters */}
        <div className="bg-gray-800 rounded-lg p-4 mb-6 flex gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search by username..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && loadData()}
              className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
          >
            <option value="">All Status</option>
            {activeTab === 'listings' ? (
              <>
                <option value="active">Active</option>
                <option value="sold">Sold</option>
                <option value="cancelled">Cancelled</option>
                <option value="removed">Removed</option>
              </>
            ) : (
              <>
                <option value="completed">Completed</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
                <option value="refunded">Refunded</option>
              </>
            )}
          </select>
          {activeTab === 'transactions' && (
            <button
              onClick={handleExportTransactions}
              className="bg-green-600 hover:bg-green-700 px-6 py-2 rounded font-semibold transition-colors"
            >
              Export CSV
            </button>
          )}
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : (
          <>
            {activeTab === 'listings' && (
              <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Listing ID</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Seller</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Price (BDT)</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Type</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Status</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Created</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {listings.map((listing) => (
                      <tr key={listing.listing_id} className="hover:bg-gray-750">
                        <td className="px-6 py-4 text-sm text-gray-300 font-mono">{listing.listing_id.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm text-gray-300">{listing.seller_id.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm text-gray-300 font-semibold">{listing.price_bdt.toLocaleString()}</td>
                        <td className="px-6 py-4 text-sm text-gray-300 capitalize">{listing.listing_type}</td>
                        <td className="px-6 py-4 text-sm">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            listing.status === 'active' ? 'bg-green-900 text-green-200' :
                            listing.status === 'sold' ? 'bg-blue-900 text-blue-200' :
                            listing.status === 'removed' ? 'bg-red-900 text-red-200' :
                            'bg-gray-700 text-gray-300'
                          }`}>
                            {listing.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">{new Date(listing.created_at).toLocaleDateString()}</td>
                        <td className="px-6 py-4 text-sm">
                          {listing.status === 'active' && (
                            <button
                              onClick={() => handleRemoveListing(listing.listing_id)}
                              className="text-red-400 hover:text-red-300 font-semibold"
                            >
                              Remove
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {listings.length === 0 && (
                  <div className="text-center py-12 text-gray-400">
                    No listings found
                  </div>
                )}
              </div>
            )}

            {activeTab === 'transactions' && (
              <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Transaction ID</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Buyer</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Seller</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Amount (BDT)</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Status</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Created</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {transactions.map((txn) => (
                      <tr key={txn.transaction_id} className="hover:bg-gray-750">
                        <td className="px-6 py-4 text-sm text-gray-300 font-mono">{txn.transaction_id.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm text-gray-300">{txn.buyer_id.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm text-gray-300">{txn.seller_id.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm text-gray-300 font-semibold">{txn.amount_bdt.toLocaleString()}</td>
                        <td className="px-6 py-4 text-sm">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            txn.status === 'completed' ? 'bg-green-900 text-green-200' :
                            txn.status === 'pending' ? 'bg-yellow-900 text-yellow-200' :
                            txn.status === 'refunded' ? 'bg-blue-900 text-blue-200' :
                            'bg-red-900 text-red-200'
                          }`}>
                            {txn.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">{new Date(txn.created_at).toLocaleDateString()}</td>
                        <td className="px-6 py-4 text-sm">
                          {txn.status === 'completed' && (
                            <button
                              onClick={() => handleRefundTransaction(txn.transaction_id)}
                              className="text-yellow-400 hover:text-yellow-300 font-semibold"
                            >
                              Refund
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {transactions.length === 0 && (
                  <div className="text-center py-12 text-gray-400">
                    No transactions found
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

export default AdminMarketplacePage;
