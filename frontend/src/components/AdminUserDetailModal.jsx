/**
 * AdminUserDetailModal Component
 * Shows comprehensive user details with management actions
 */

import { useState, useEffect } from "react";
import { adminAPI, usersAPI } from "../services/api";
import toast from "react-hot-toast";
import UserProfileCard from "./UserProfileCard";
import TransactionHistory from "./TransactionHistory";

function AdminUserDetailModal({ user, onClose, onUserUpdated }) {
  const [activeTab, setActiveTab] = useState("profile");
  const [isBanning, setIsBanning] = useState(false);
  const [banReason, setBanReason] = useState(user?.ban_reason || "");
  const [isEditingBan, setIsEditingBan] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isAdjustingBalance, setIsAdjustingBalance] = useState(false);
  const [balanceAmount, setBalanceAmount] = useState("");
  const [balanceAction, setBalanceAction] = useState("add");

  const handleBanUser = async () => {
    try {
      setIsBanning(true);
      await adminAPI.banUser(user.user_id, { reason: banReason });
      toast.success("User banned successfully");
      onUserUpdated();
      onClose();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to ban user");
    } finally {
      setIsBanning(false);
    }
  };

  const handleUnbanUser = async () => {
    try {
      setIsBanning(true);
      await adminAPI.unbanUser(user.user_id);
      toast.success("User unbanned successfully");
      onUserUpdated();
      onClose();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to unban user");
    } finally {
      setIsBanning(false);
    }
  };

  const handleVerify = async (flag) => {
    try {
      setIsVerifying(true);
      if (flag) {
        await adminAPI.verifyUser(user.user_id);
        toast.success("User verified");
      } else {
        await adminAPI.unverifyUser(user.user_id);
        toast.success("User unverified");
      }
      onUserUpdated();
      onClose();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Verification update failed");
    } finally {
      setIsVerifying(false);
    }
  };

  const handleBalanceAdjustment = async () => {
    const amount = parseInt(balanceAmount);
    if (isNaN(amount) || amount <= 0) {
      toast.error("Please enter a valid positive amount");
      return;
    }

    try {
      setIsBanning(true);
      const currentBalance = user.balance_bdt || 0;
      const newBalance =
        balanceAction === "add"
          ? currentBalance + amount
          : currentBalance - amount;

      if (newBalance < 0) {
        toast.error("Cannot deduct more than current balance");
        return;
      }

      await adminAPI.updateUser(user.user_id, { balance_bdt: newBalance });
      toast.success(
        `Balance ${balanceAction === "add" ? "added" : "deducted"} successfully`
      );
      setBalanceAmount("");
      setIsAdjustingBalance(false);
      onUserUpdated();
      onClose();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to adjust balance");
    } finally {
      setIsBanning(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-gray-800 rounded-lg border border-gray-700 max-w-2xl w-full my-8">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-gray-700">
          <div className="flex items-center gap-4">
            {user?.avatar_url && (
              <img
                src={user.avatar_url}
                alt={user.username}
                className="w-12 h-12 rounded-full bg-gray-700 object-cover border-2 border-blue-600"
              />
            )}
            <div>
              <h2 className="text-xl font-bold">{user?.username}</h2>
              <p className="text-sm text-gray-400">{user?.email}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-700 bg-gray-900">
          <button
            onClick={() => setActiveTab("profile")}
            className={`flex-1 px-4 py-3 text-sm font-semibold transition-colors ${
              activeTab === "profile"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-gray-300"
            }`}
          >
            Profile
          </button>
          <button
            onClick={() => setActiveTab("transactions")}
            className={`flex-1 px-4 py-3 text-sm font-semibold transition-colors ${
              activeTab === "transactions"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-gray-300"
            }`}
          >
            Transactions
          </button>
          <button
            onClick={() => setActiveTab("actions")}
            className={`flex-1 px-4 py-3 text-sm font-semibold transition-colors ${
              activeTab === "actions"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-gray-300"
            }`}
          >
            Actions
          </button>
        </div>

        {/* Content */}
        <div className="p-6 max-h-[70vh] overflow-y-auto">
          {activeTab === "profile" && (
            <div className="space-y-6">
              <div className="bg-gray-700 rounded-lg p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-400">User ID</p>
                    <p className="text-xs font-mono text-gray-300 break-all">
                      {user?.user_id}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">Role</p>
                    <p className="font-semibold capitalize">{user?.role}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">Balance</p>
                    <p className="font-semibold text-green-400">
                      {user?.balance_bdt?.toLocaleString()} BDT
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">Verified</p>
                    <p className="font-semibold flex items-center gap-2">
                      {user?.verified ? "Yes" : "No"}
                      <button
                        onClick={() => handleVerify(!user?.verified)}
                        disabled={isVerifying}
                        className="text-xs px-2 py-1 rounded bg-blue-700 hover:bg-blue-600 disabled:opacity-50"
                      >
                        {user?.verified ? "Unverify" : "Verify"}
                      </button>
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">Registered</p>
                    <p className="font-semibold">
                      {user?.created_at
                        ? new Date(user.created_at).toLocaleDateString()
                        : "N/A"}
                    </p>
                  </div>
                  <div className="col-span-2">
                    <p className="text-sm text-gray-400">Bio</p>
                    <p className="text-sm text-gray-200 whitespace-pre-line bg-gray-800/80 border border-gray-600 rounded p-2">
                      {user?.bio || "—"}
                    </p>
                  </div>
                </div>
              </div>

              {user?.is_banned && (
                <div className="bg-red-900/20 border border-red-700 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <svg
                      className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <div>
                      <p className="font-semibold text-red-300">
                        User is Banned
                      </p>
                      <p className="text-sm text-red-300 mt-1">
                        {user.ban_reason}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {user?.stats && (
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-gray-700 rounded-lg p-4">
                    <p className="text-sm text-gray-400 mb-1">Lands Owned</p>
                    <p className="text-2xl font-bold text-green-400">
                      {user.stats.lands_owned}
                    </p>
                  </div>
                  <div className="bg-gray-700 rounded-lg p-4">
                    <p className="text-sm text-gray-400 mb-1">Transactions</p>
                    <p className="text-2xl font-bold text-blue-400">
                      {user.stats.total_transactions}
                    </p>
                  </div>
                  <div className="bg-gray-700 rounded-lg p-4">
                    <p className="text-sm text-gray-400 mb-1">Land Value</p>
                    <p className="text-2xl font-bold text-purple-400">
                      {(user.stats.total_land_value_bdt || 0).toLocaleString()}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === "transactions" && (
            <TransactionHistory userId={user?.user_id} />
          )}

          {activeTab === "actions" && (
            <div className="space-y-4">
              {/* Balance Management */}
              <div className="bg-gray-700 rounded-lg p-4 border border-gray-600">
                <h3 className="font-semibold mb-3">Balance Management</h3>
                {!isAdjustingBalance ? (
                  <button
                    onClick={() => setIsAdjustingBalance(true)}
                    className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-semibold"
                  >
                    Adjust Balance
                  </button>
                ) : (
                  <div className="space-y-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => setBalanceAction("add")}
                        className={`flex-1 px-3 py-2 rounded-lg font-semibold transition-colors ${
                          balanceAction === "add"
                            ? "bg-green-600 text-white"
                            : "bg-gray-600 text-gray-300 hover:bg-gray-500"
                        }`}
                      >
                        Add Money
                      </button>
                      <button
                        onClick={() => setBalanceAction("deduct")}
                        className={`flex-1 px-3 py-2 rounded-lg font-semibold transition-colors ${
                          balanceAction === "deduct"
                            ? "bg-red-600 text-white"
                            : "bg-gray-600 text-gray-300 hover:bg-gray-500"
                        }`}
                      >
                        Deduct Money
                      </button>
                    </div>
                    <input
                      type="number"
                      value={balanceAmount}
                      onChange={(e) => setBalanceAmount(e.target.value)}
                      placeholder="Amount (BDT)"
                      min="1"
                      className="w-full px-3 py-2 bg-gray-600 border border-gray-500 rounded-lg text-white focus:outline-none focus:border-blue-500"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={handleBalanceAdjustment}
                        disabled={isBanning || !balanceAmount}
                        className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors font-semibold"
                      >
                        {isBanning ? "Processing..." : "Confirm"}
                      </button>
                      <button
                        onClick={() => {
                          setIsAdjustingBalance(false);
                          setBalanceAmount("");
                        }}
                        className="flex-1 px-4 py-2 bg-gray-600 hover:bg-gray-500 text-white rounded-lg transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Ban Section */}
              <div className="bg-gray-700 rounded-lg p-4 border border-gray-600">
                <h3 className="font-semibold mb-3">Ban Management</h3>

                {user?.is_banned ? (
                  <div>
                    <p className="text-sm text-gray-400 mb-3">
                      User is currently banned
                    </p>
                    <button
                      onClick={handleUnbanUser}
                      disabled={isBanning}
                      className="w-full px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-semibold"
                    >
                      {isBanning ? "Processing..." : "Unban User"}
                    </button>
                  </div>
                ) : (
                  <div>
                    {!isEditingBan ? (
                      <button
                        onClick={() => setIsEditingBan(true)}
                        className="w-full px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors font-semibold"
                      >
                        Ban User
                      </button>
                    ) : (
                      <div className="space-y-3">
                        <textarea
                          value={banReason}
                          onChange={(e) =>
                            setBanReason(e.target.value.slice(0, 500))
                          }
                          placeholder="Ban reason (optional)..."
                          maxLength={500}
                          className="w-full px-3 py-2 bg-gray-600 border border-gray-500 rounded-lg text-white focus:outline-none focus:border-red-500 resize-none"
                          rows={3}
                        />
                        <p className="text-xs text-gray-400">
                          {banReason.length}/500 characters
                        </p>
                        <div className="flex gap-2">
                          <button
                            onClick={handleBanUser}
                            disabled={isBanning}
                            className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg transition-colors font-semibold"
                          >
                            {isBanning ? "Processing..." : "Confirm Ban"}
                          </button>
                          <button
                            onClick={() => {
                              setIsEditingBan(false);
                              setBanReason(user?.ban_reason || "");
                            }}
                            className="flex-1 px-4 py-2 bg-gray-600 hover:bg-gray-500 text-white rounded-lg transition-colors"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Account Info */}
              <div className="bg-gray-700 rounded-lg p-4 border border-gray-600">
                <h3 className="font-semibold mb-3">Account Information</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Current Balance:</span>
                    <span className="font-semibold text-green-400">
                      {user?.balance_bdt?.toLocaleString()} BDT
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Email Verified:</span>
                    <span className="font-semibold">
                      {user?.verified ? "✓ Yes" : "✗ No"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Account Age:</span>
                    <span className="font-semibold">
                      {user?.created_at
                        ? Math.floor(
                            (Date.now() - new Date(user.created_at).getTime()) /
                              (1000 * 60 * 60 * 24)
                          )
                        : 0}{" "}
                      days
                    </span>
                  </div>
                </div>
              </div>

              {/* Danger Zone */}
              <div className="bg-red-900/20 border border-red-700 rounded-lg p-4">
                <h3 className="font-semibold text-red-300 mb-3">Danger Zone</h3>
                <p className="text-sm text-gray-400 mb-3">
                  These actions cannot be undone
                </p>
                <button
                  disabled
                  className="w-full px-4 py-2 bg-red-900/50 text-red-300 rounded-lg border border-red-700 cursor-not-allowed opacity-50 font-semibold"
                >
                  Delete Account (Coming Soon)
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AdminUserDetailModal;
