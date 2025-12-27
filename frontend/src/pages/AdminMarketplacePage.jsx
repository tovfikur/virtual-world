/**
 * Admin Marketplace Management Page
 * View and moderate marketplace listings and transactions
 */

import { useState, useEffect } from "react";
import { adminAPI } from "../services/api";
import useAuthStore from "../stores/authStore";
import toast from "react-hot-toast";

function AdminMarketplacePage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState("listings");
  const [listings, setListings] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [paymentConfig, setPaymentConfig] = useState({
    enable_gateway_bkash: true,
    enable_gateway_nagad: true,
    topup_max_bdt: 50000,
    gateway_fee_mode: "absorb", // 'absorb' | 'pass-through'
    gateway_fee_percent: 1.5,
    gateway_fee_flat_bdt: 0,
  });
  const [savingPayments, setSavingPayments] = useState(false);

  useEffect(() => {
    if (user?.role !== "admin") {
      toast.error("Admin access required");
      return;
    }
    loadData();
    if (activeTab === "payments") {
      loadPaymentConfig();
    }
  }, [user, page, statusFilter, activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === "listings") {
        const res = await adminAPI.getMarketplaceListings({
          page,
          status: statusFilter,
          search: searchQuery,
        });
        setListings(res.data.data);
        setPagination(res.data.pagination);
      } else if (activeTab === "transactions") {
        const res = await adminAPI.getTransactions({
          page,
          status: statusFilter,
          search: searchQuery,
        });
        setTransactions(res.data.data);
        setPagination(res.data.pagination);
      }
    } catch (error) {
      toast.error("Failed to load data");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const loadPaymentConfig = async () => {
    try {
      const [featuresRes, limitsRes] = await Promise.all([
        adminAPI.getFeatureToggles(),
        adminAPI.getSystemLimits(),
      ]);
      setPaymentConfig((prev) => ({
        ...prev,
        enable_gateway_bkash: !!featuresRes.data?.enable_gateway_bkash,
        enable_gateway_nagad: !!featuresRes.data?.enable_gateway_nagad,
        topup_max_bdt: limitsRes.data?.topup_max_bdt ?? prev.topup_max_bdt,
        gateway_fee_mode:
          limitsRes.data?.gateway_fee_mode || prev.gateway_fee_mode,
        gateway_fee_percent:
          limitsRes.data?.gateway_fee_percent ?? prev.gateway_fee_percent,
        gateway_fee_flat_bdt:
          limitsRes.data?.gateway_fee_flat_bdt ?? prev.gateway_fee_flat_bdt,
      }));
    } catch (error) {
      console.error(error);
    }
  };

  const handleRemoveListing = async (listingId) => {
    const reason = prompt("Enter reason for removal:");
    if (!reason) return;

    try {
      await adminAPI.removeListing(listingId, reason);
      toast.success("Listing removed successfully");
      loadData();
    } catch (error) {
      toast.error("Failed to remove listing");
      console.error(error);
    }
  };

  const handleRefundTransaction = async (transactionId) => {
    const reason = prompt("Enter reason for refund:");
    if (!reason) return;

    const confirmed = window.confirm(
      "Are you sure you want to refund this transaction? This action cannot be undone."
    );
    if (!confirmed) return;

    try {
      await adminAPI.refundTransaction(transactionId, reason);
      toast.success("Transaction refunded successfully");
      loadData();
    } catch (error) {
      toast.error("Failed to refund transaction");
      console.error(error);
    }
  };

  const handleExportTransactions = async () => {
    try {
      const res = await adminAPI.exportTransactions();
      // Convert to CSV and download
      const csvContent = convertToCSV(res.data.data);
      downloadCSV(csvContent, "transactions.csv");
      toast.success("Transactions exported successfully");
    } catch (error) {
      toast.error("Failed to export transactions");
      console.error(error);
    }
  };

  const handleSavePayments = async () => {
    if (paymentConfig.topup_max_bdt < 1) {
      toast.error("Top-up limit must be >= 1");
      return;
    }
    if (
      paymentConfig.gateway_fee_percent < 0 ||
      paymentConfig.gateway_fee_percent > 100
    ) {
      toast.error("Fee percent must be 0-100");
      return;
    }
    setSavingPayments(true);
    try {
      await adminAPI.updateFeatureToggles({
        enable_gateway_bkash: paymentConfig.enable_gateway_bkash,
        enable_gateway_nagad: paymentConfig.enable_gateway_nagad,
      });
      await adminAPI.updateSystemLimits({
        topup_max_bdt: paymentConfig.topup_max_bdt,
        gateway_fee_mode: paymentConfig.gateway_fee_mode,
        gateway_fee_percent: paymentConfig.gateway_fee_percent,
        gateway_fee_flat_bdt: paymentConfig.gateway_fee_flat_bdt,
      });
      toast.success("Payment settings saved");
    } catch (error) {
      toast.error("Failed to save payment settings");
      console.error(error);
    } finally {
      setSavingPayments(false);
    }
  };

  const convertToCSV = (data) => {
    if (!data || data.length === 0) return "";

    const headers = Object.keys(data[0]).join(",");
    const rows = data.map((row) => Object.values(row).join(",")).join("\n");
    return `${headers}\n${rows}`;
  };

  const downloadCSV = (content, filename) => {
    const blob = new Blob([content], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
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
          <h1 className="text-3xl font-bold mb-2">Marketplace Management</h1>
          <p className="text-gray-400">
            Moderate listings and manage transactions
          </p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {/* Tabs */}
        <div className="flex space-x-4 mb-6 border-b border-gray-700">
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "listings"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => {
              setActiveTab("listings");
              setPage(1);
            }}
          >
            Listings
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "transactions"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => {
              setActiveTab("transactions");
              setPage(1);
            }}
          >
            Transactions
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "payments"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => {
              setActiveTab("payments");
              setPage(1);
            }}
          >
            Payments
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
              onKeyDown={(e) => e.key === "Enter" && loadData()}
              className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
          >
            <option value="">All Status</option>
            {activeTab === "listings" ? (
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
          {activeTab === "transactions" && (
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
            {activeTab === "listings" && (
              <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Listing ID
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Seller
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Price (BDT)
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Type
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Status
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
                    {listings.map((listing) => (
                      <tr
                        key={listing.listing_id}
                        className="hover:bg-gray-750"
                      >
                        <td className="px-6 py-4 text-sm text-gray-300 font-mono">
                          {listing.listing_id.substring(0, 8)}...
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-300">
                          {listing.seller_id.substring(0, 8)}...
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-300 font-semibold">
                          {listing.price_bdt.toLocaleString()}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-300 capitalize">
                          {listing.listing_type}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <span
                            className={`px-2 py-1 rounded text-xs font-semibold ${
                              listing.status === "active"
                                ? "bg-green-900 text-green-200"
                                : listing.status === "sold"
                                ? "bg-blue-900 text-blue-200"
                                : listing.status === "removed"
                                ? "bg-red-900 text-red-200"
                                : "bg-gray-700 text-gray-300"
                            }`}
                          >
                            {listing.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">
                          {new Date(listing.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          {listing.status === "active" && (
                            <button
                              onClick={() =>
                                handleRemoveListing(listing.listing_id)
                              }
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

            {activeTab === "transactions" && (
              <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-700">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Transaction ID
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Buyer
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Seller
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Amount (BDT)
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase">
                        Status
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
                    {transactions.map((txn) => (
                      <tr
                        key={txn.transaction_id}
                        className="hover:bg-gray-750"
                      >
                        <td className="px-6 py-4 text-sm text-gray-300 font-mono">
                          {txn.transaction_id.substring(0, 8)}...
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-300">
                          {txn.buyer_id.substring(0, 8)}...
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-300">
                          {txn.seller_id
                            ? txn.seller_id.substring(0, 8) + "..."
                            : "N/A"}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-300 font-semibold">
                          {txn.amount_bdt.toLocaleString()}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <span
                            className={`px-2 py-1 rounded text-xs font-semibold ${
                              (txn.status || "").toLowerCase() === "completed"
                                ? "bg-green-900 text-green-200"
                                : (txn.status || "").toLowerCase() === "pending"
                                ? "bg-yellow-900 text-yellow-200"
                                : (txn.status || "").toLowerCase() ===
                                  "refunded"
                                ? "bg-blue-900 text-blue-200"
                                : "bg-red-900 text-red-200"
                            }`}
                          >
                            {typeof txn.status === "string"
                              ? txn.status
                              : txn.status?.toString?.() || "UNKNOWN"}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">
                          {new Date(txn.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          {txn.status === "completed" && (
                            <button
                              onClick={() =>
                                handleRefundTransaction(txn.transaction_id)
                              }
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

            {activeTab === "payments" && (
              <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 className="text-xl font-bold mb-4">
                  Payment Gateway Settings
                </h3>
                <div className="space-y-6">
                  <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
                    <div>
                      <h4 className="font-semibold mb-1">Enable bKash</h4>
                      <p className="text-sm text-gray-400">
                        Toggle bKash gateway availability
                      </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={paymentConfig.enable_gateway_bkash}
                        onChange={(e) =>
                          setPaymentConfig({
                            ...paymentConfig,
                            enable_gateway_bkash: e.target.checked,
                          })
                        }
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-600 rounded-full peer peer-checked:bg-blue-600"></div>
                    </label>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
                    <div>
                      <h4 className="font-semibold mb-1">Enable Nagad</h4>
                      <p className="text-sm text-gray-400">
                        Toggle Nagad gateway availability
                      </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={paymentConfig.enable_gateway_nagad}
                        onChange={(e) =>
                          setPaymentConfig({
                            ...paymentConfig,
                            enable_gateway_nagad: e.target.checked,
                          })
                        }
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-600 rounded-full peer peer-checked:bg-blue-600"></div>
                    </label>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Top-up Max (BDT)
                      </label>
                      <input
                        type="number"
                        value={paymentConfig.topup_max_bdt}
                        onChange={(e) =>
                          setPaymentConfig({
                            ...paymentConfig,
                            topup_max_bdt: parseInt(e.target.value || "0"),
                          })
                        }
                        className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Gateway Fee Mode
                      </label>
                      <select
                        value={paymentConfig.gateway_fee_mode}
                        onChange={(e) =>
                          setPaymentConfig({
                            ...paymentConfig,
                            gateway_fee_mode: e.target.value,
                          })
                        }
                        className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                      >
                        <option value="absorb">Platform Absorbs Fees</option>
                        <option value="pass-through">
                          Pass-through to Users
                        </option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Gateway Fee Percent (%)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        value={paymentConfig.gateway_fee_percent}
                        onChange={(e) =>
                          setPaymentConfig({
                            ...paymentConfig,
                            gateway_fee_percent: parseFloat(
                              e.target.value || "0"
                            ),
                          })
                        }
                        className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Gateway Flat Fee (BDT)
                      </label>
                      <input
                        type="number"
                        value={paymentConfig.gateway_fee_flat_bdt}
                        onChange={(e) =>
                          setPaymentConfig({
                            ...paymentConfig,
                            gateway_fee_flat_bdt: parseInt(
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
                      onClick={handleSavePayments}
                      disabled={savingPayments}
                      className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-8 py-3 rounded font-semibold transition-colors"
                    >
                      {savingPayments ? "Saving..." : "Save Payment Settings"}
                    </button>
                  </div>

                  <div className="mt-8 bg-gray-700 rounded p-4 border border-gray-600">
                    <h4 className="font-semibold mb-2">Monitoring Summary</h4>
                    <p className="text-sm text-gray-300">
                      Use Transactions tab to filter failed/pending payments;
                      reconciliation summary will be enhanced in a dedicated
                      report.
                    </p>
                  </div>
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

export default AdminMarketplacePage;
