/**
 * TransactionHistory Component
 * Displays user's transaction history with filtering and pagination
 */

import { useState, useEffect } from 'react';
import { usersAPI } from '../services/api';
import toast from 'react-hot-toast';

function TransactionHistory({ userId }) {
  const [transactions, setTransactions] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [filterType, setFilterType] = useState('all');

  useEffect(() => {
    loadTransactions(currentPage);
  }, [userId, currentPage]);

  const loadTransactions = async (page) => {
    try {
      setIsLoading(true);
      const res = await usersAPI.getTransactions(userId, page, 10);
      
      setTransactions(res.data.transactions || []);
      setPagination(res.data.pagination);
    } catch (error) {
      toast.error('Failed to load transactions');
      console.error('Transaction load error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredTransactions = filterType === 'all'
    ? transactions
    : transactions.filter(t => t.transaction_type === filterType);

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-BD', {
      style: 'currency',
      currency: 'BDT'
    }).format(amount);
  };

  const getTransactionTypeColor = (type) => {
    const colors = {
      'AUCTION': 'bg-blue-900',
      'BUY_NOW': 'bg-green-900',
      'FIXED_PRICE': 'bg-purple-900',
      'TRANSFER': 'bg-gray-700',
      'TOPUP': 'bg-yellow-900',
      'BIOME_BUY': 'bg-cyan-900',
      'BIOME_SELL': 'bg-orange-900'
    };
    return colors[type] || 'bg-gray-700';
  };

  const getStatusColor = (status) => {
    const colors = {
      'COMPLETED': 'text-green-400',
      'PENDING': 'text-yellow-400',
      'FAILED': 'text-red-400',
      'REFUNDED': 'text-orange-400'
    };
    return colors[status] || 'text-gray-400';
  };

  if (isLoading && transactions.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-lg font-semibold mb-4">Transaction History</h2>
        <div className="flex justify-center">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h2 className="text-lg font-semibold mb-4">Transaction History</h2>

      {/* Filter */}
      <div className="mb-4">
        <select
          value={filterType}
          onChange={(e) => {
            setFilterType(e.target.value);
            setCurrentPage(1);
          }}
          className="px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-lg focus:outline-none focus:border-blue-500"
        >
          <option value="all">All Transactions</option>
          <option value="AUCTION">Auctions</option>
          <option value="BUY_NOW">Buy Now</option>
          <option value="FIXED_PRICE">Fixed Price</option>
          <option value="TRANSFER">Transfers</option>
          <option value="TOPUP">Top Ups</option>
          <option value="BIOME_BUY">Biome Purchases</option>
          <option value="BIOME_SELL">Biome Sales</option>
        </select>
      </div>

      {/* Transactions List */}
      {filteredTransactions.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <svg className="w-12 h-12 mx-auto mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p>No transactions yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTransactions.map((tx) => (
            <div key={tx.transaction_id} className="bg-gray-700 rounded-lg p-4 border border-gray-600 hover:border-gray-500 transition-colors">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-1 rounded text-xs font-semibold text-white ${getTransactionTypeColor(tx.transaction_type)}`}>
                    {tx.transaction_type.replace(/_/g, ' ')}
                  </span>
                  <span className={`text-xs font-semibold ${getStatusColor(tx.status)}`}>
                    {tx.status}
                  </span>
                </div>
                <span className="text-lg font-bold text-white">
                  {formatCurrency(tx.amount_bdt)}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs text-gray-400">
                {tx.biome && (
                  <div>
                    <span className="text-gray-500">Biome:</span> {tx.biome}
                  </div>
                )}
                {tx.shares && (
                  <div>
                    <span className="text-gray-500">Shares:</span> {tx.shares.toFixed(2)}
                  </div>
                )}
                {tx.gateway_name && (
                  <div>
                    <span className="text-gray-500">Gateway:</span> {tx.gateway_name}
                  </div>
                )}
                {tx.platform_fee_bdt > 0 && (
                  <div>
                    <span className="text-gray-500">Platform Fee:</span> {formatCurrency(tx.platform_fee_bdt)}
                  </div>
                )}
              </div>

              <div className="mt-2 text-xs text-gray-500">
                {tx.created_at ? new Date(tx.created_at).toLocaleString() : 'N/A'}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {pagination && pagination.pages > 1 && (
        <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-600">
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={!pagination.has_prev || isLoading}
            className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          >
            Previous
          </button>

          <span className="text-sm text-gray-400">
            Page {pagination.page} of {pagination.pages}
          </span>

          <button
            onClick={() => setCurrentPage(p => Math.min(pagination.pages, p + 1))}
            disabled={!pagination.has_next || isLoading}
            className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

export default TransactionHistory;
