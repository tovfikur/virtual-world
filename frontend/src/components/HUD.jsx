/**
 * HUD Component
 * Top bar with user info and navigation
 */

import { Link, useNavigate } from "react-router-dom";
import useAuthStore from "../stores/authStore";
import { wsAPI } from "../services/api";
import { useEffect, useState } from "react";

function HUD() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [onlineCount, setOnlineCount] = useState(0);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showMobileMenu, setShowMobileMenu] = useState(false);

  useEffect(() => {
    // Load online users count
    const loadOnlineCount = async () => {
      try {
        const response = await wsAPI.getOnlineUsers();
        setOnlineCount(response.data.count);
      } catch (error) {
        console.error("Failed to load online count:", error);
      }
    };

    loadOnlineCount();
    const interval = setInterval(loadOnlineCount, 30000); // Update every 30s

    return () => clearInterval(interval);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  if (!user) return null;

  return (
    <div className="absolute top-0 left-0 right-0 z-10 bg-gray-800/95 backdrop-blur-sm border-b border-gray-700">
      {/* Main Header */}
      <div className="flex items-center justify-between px-3 sm:px-6 py-2.5 sm:py-3">
        {/* Left - Logo & Hamburger */}
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setShowMobileMenu(!showMobileMenu)}
            className="md:hidden text-gray-300 hover:text-white p-1"
          >
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              {showMobileMenu ? (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              ) : (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              )}
            </svg>
          </button>
          <h1 className="text-base sm:text-xl font-bold text-white truncate">
            Virtual Land World
          </h1>
        </div>

        {/* Desktop Nav */}
        <nav className="hidden md:flex space-x-6">
          <Link
            to="/world"
            className="text-gray-300 hover:text-white transition-colors font-medium"
          >
            World
          </Link>
          <Link
            to="/marketplace"
            className="text-gray-300 hover:text-white transition-colors font-medium"
          >
            Marketplace
          </Link>
          <Link
            to="/biome-market"
            className="text-cyan-400 hover:text-cyan-300 transition-colors font-medium"
          >
            Biome Market
          </Link>
          <Link
            to="/profile"
            className="text-gray-300 hover:text-white transition-colors font-medium"
          >
            Profile
          </Link>
        </nav>

        {/* Right - Online Count & User */}
        <div className="flex items-center space-x-3 sm:space-x-4">
          {/* Online Count */}
          <div className="hidden sm:flex items-center space-x-2 text-xs sm:text-sm text-gray-300">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span>{onlineCount}</span>
          </div>

          {/* User Info */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center space-x-2 bg-gray-700 hover:bg-gray-600 px-2 sm:px-4 py-1.5 sm:py-2 rounded-lg transition-colors"
            >
              <div className="text-right">
                <p className="text-white font-semibold text-xs sm:text-sm">
                  {user.username}
                </p>
                <p className="text-[10px] sm:text-xs text-green-400">
                  {user.balance_bdt} BDT
                </p>
              </div>
              <svg
                className="w-4 h-4 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>

            {/* Desktop Dropdown Menu */}
            {showUserMenu && (
              <div className="absolute right-0 mt-2 w-48 bg-gray-800 rounded-lg shadow-xl border border-gray-700 overflow-hidden z-20">
                <Link
                  to="/profile"
                  className="block px-4 py-3 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors"
                  onClick={() => setShowUserMenu(false)}
                >
                  My Profile
                </Link>
                <Link
                  to="/marketplace"
                  className="block px-4 py-3 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors"
                  onClick={() => setShowUserMenu(false)}
                >
                  Marketplace
                </Link>
                {user.role === "admin" && (
                  <Link
                    to="/admin"
                    className="block px-4 py-3 hover:bg-gray-700 text-yellow-400 hover:text-yellow-300 transition-colors border-t border-gray-700"
                    onClick={() => setShowUserMenu(false)}
                  >
                    Admin Dashboard
                  </Link>
                )}
                <button
                  onClick={handleLogout}
                  className="w-full text-left px-4 py-3 hover:bg-gray-700 text-red-400 hover:text-red-300 transition-colors border-t border-gray-700"
                >
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {showMobileMenu && (
        <div className="md:hidden bg-gray-800/98 border-t border-gray-700">
          <nav className="flex flex-col">
            <Link
              to="/world"
              className="px-4 py-3 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors border-b border-gray-700/50"
              onClick={() => setShowMobileMenu(false)}
            >
              🌍 World
            </Link>
            <Link
              to="/marketplace"
              className="px-4 py-3 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors border-b border-gray-700/50"
              onClick={() => setShowMobileMenu(false)}
            >
              🏪 Marketplace
            </Link>
            <Link
              to="/biome-market"
              className="px-4 py-3 text-cyan-400 hover:bg-gray-700 hover:text-cyan-300 transition-colors border-b border-gray-700/50"
              onClick={() => setShowMobileMenu(false)}
            >
              💎 Biome Market
            </Link>
            <Link
              to="/profile"
              className="px-4 py-3 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors border-b border-gray-700/50"
              onClick={() => setShowMobileMenu(false)}
            >
              👤 Profile
            </Link>
            {user.role === "admin" && (
              <Link
                to="/admin"
                className="px-4 py-3 text-yellow-400 hover:bg-gray-700 hover:text-yellow-300 transition-colors border-b border-gray-700/50"
                onClick={() => setShowMobileMenu(false)}
              >
                ⚙️ Admin Dashboard
              </Link>
            )}
            <div className="px-4 py-3 text-gray-400 text-sm border-b border-gray-700/50 flex items-center justify-between">
              <span>Online Users</span>
              <span className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-green-400 font-semibold">
                  {onlineCount}
                </span>
              </span>
            </div>
            <button
              onClick={() => {
                handleLogout();
                setShowMobileMenu(false);
              }}
              className="px-4 py-3 text-red-400 hover:bg-gray-700 hover:text-red-300 transition-colors text-left"
            >
              🚪 Logout
            </button>
          </nav>
        </div>
      )}
    </div>
  );
}

export default HUD;
