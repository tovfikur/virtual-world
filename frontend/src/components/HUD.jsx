/**
 * HUD Component
 * Top bar with user info and navigation
 */

import { Link, useNavigate } from 'react-router-dom';
import useAuthStore from '../stores/authStore';
import { wsAPI } from '../services/api';
import { useEffect, useState } from 'react';

function HUD() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [onlineCount, setOnlineCount] = useState(0);
  const [showUserMenu, setShowUserMenu] = useState(false);

  useEffect(() => {
    // Load online users count
    const loadOnlineCount = async () => {
      try {
        const response = await wsAPI.getOnlineUsers();
        setOnlineCount(response.data.count);
      } catch (error) {
        console.error('Failed to load online count:', error);
      }
    };

    loadOnlineCount();
    const interval = setInterval(loadOnlineCount, 30000); // Update every 30s

    return () => clearInterval(interval);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  if (!user) return null;

  return (
    <div className="absolute top-0 left-0 right-0 z-10 bg-gray-800/90 backdrop-blur-sm border-b border-gray-700">
      <div className="flex flex-col sm:flex-row items-center justify-between px-4 sm:px-6 py-3 gap-2 sm:gap-0">
        {/* Left - Logo & Nav */}
        <div className="flex items-center space-x-3 sm:space-x-6">
          <h1 className="text-lg sm:text-xl font-bold text-white">Virtual Land World</h1>
          <nav className="hidden md:flex space-x-4">
            <Link
              to="/world"
              className="text-gray-300 hover:text-white transition-colors"
            >
              World
            </Link>
            <Link
              to="/marketplace"
              className="text-gray-300 hover:text-white transition-colors"
            >
              Marketplace
            </Link>
            <Link
              to="/profile"
              className="text-gray-300 hover:text-white transition-colors"
            >
              Profile
            </Link>
          </nav>
        </div>

        {/* Center - Online Count */}
        <div className="flex items-center space-x-2 text-sm text-gray-300">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span>{onlineCount} online</span>
        </div>

        {/* Right - User Info */}
        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center space-x-3 bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg transition-colors"
          >
            <div className="text-right">
              <p className="text-white font-semibold">{user.username}</p>
              <p className="text-xs text-green-400">{user.balance_bdt} BDT</p>
            </div>
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Dropdown Menu */}
          {showUserMenu && (
            <div className="absolute right-0 mt-2 w-48 bg-gray-800 rounded-lg shadow-xl border border-gray-700 overflow-hidden">
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
              {user.role === 'admin' && (
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
                className="w-full text-left px-4 py-3 hover:bg-gray-700 text-red-400 hover:text-red-300 transition-colors"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default HUD;
