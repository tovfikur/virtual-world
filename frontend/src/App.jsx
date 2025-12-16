/**
 * Main App Component
 * Root component with routing and global providers
 */

import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster, toast } from 'react-hot-toast';
import useAuthStore from './stores/authStore';
import { wsService } from './services/websocket';

// Pages
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import WorldPage from './pages/WorldPage';
import MarketplacePage from './pages/MarketplacePage';
import ProfilePage from './pages/ProfilePage';

// Admin Pages
import AdminDashboardPage from './pages/AdminDashboardPage';
import AdminUsersPage from './pages/AdminUsersPage';
import AdminLogsPage from './pages/AdminLogsPage';
import AdminMarketplacePage from './pages/AdminMarketplacePage';
import AdminLandsPage from './pages/AdminLandsPage';
import AdminEconomyPage from './pages/AdminEconomyPage';
import AdminModerationPage from './pages/AdminModerationPage';
import AdminFeaturesPage from './pages/AdminFeaturesPage';
import AdminCommunicationPage from './pages/AdminCommunicationPage';
import AdminSecurityPage from './pages/AdminSecurityPage';

// Components
import ProtectedRoute from './components/ProtectedRoute';
import LoadingScreen from './components/LoadingScreen';

function App() {
  const { isAuthenticated, isLoading, loadUser } = useAuthStore();

  // Load user on mount
  useEffect(() => {
    loadUser();
  }, [loadUser]);

  // Listen for broadcast messages from admin
  useEffect(() => {
    if (!isAuthenticated) return;

    const handleBroadcast = (message) => {
      // Show a custom toast for broadcast messages
      toast.custom(
        (t) => (
          <div
            className={`${
              t.visible ? 'animate-enter' : 'animate-leave'
            } max-w-md w-full bg-gradient-to-r from-blue-600 to-purple-600 shadow-lg rounded-lg pointer-events-auto flex ring-1 ring-black ring-opacity-5`}
          >
            <div className="flex-1 w-0 p-4">
              <div className="flex items-start">
                <div className="flex-shrink-0 pt-0.5">
                  <svg className="h-10 w-10 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z" />
                  </svg>
                </div>
                <div className="ml-3 flex-1">
                  <p className="text-sm font-bold text-white">
                    {message.title || 'System Announcement'}
                  </p>
                  <p className="mt-1 text-sm text-gray-100">
                    {message.message}
                  </p>
                </div>
              </div>
            </div>
            <div className="flex border-l border-white/20">
              <button
                onClick={() => toast.dismiss(t.id)}
                className="w-full border border-transparent rounded-none rounded-r-lg p-4 flex items-center justify-center text-sm font-medium text-white hover:text-gray-200 focus:outline-none"
              >
                Close
              </button>
            </div>
          </div>
        ),
        {
          duration: 10000, // Show for 10 seconds
          position: 'top-center',
        }
      );
    };

    // Subscribe to broadcast messages
    const unsubscribe = wsService.on('broadcast', handleBroadcast);

    // Cleanup on unmount
    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, [isAuthenticated]);

  if (isLoading) {
    return <LoadingScreen />;
  }

  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: '#1f2937',
            color: '#f3f4f6',
            border: '1px solid #374151',
          },
        }}
      />

      <Routes>
        {/* Public routes */}
        <Route
          path="/login"
          element={
            isAuthenticated ? <Navigate to="/world" /> : <LoginPage />
          }
        />
        <Route
          path="/register"
          element={
            isAuthenticated ? <Navigate to="/world" /> : <RegisterPage />
          }
        />

        {/* Protected routes */}
        <Route
          path="/world"
          element={
            <ProtectedRoute>
              <WorldPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/marketplace"
          element={
            <ProtectedRoute>
              <MarketplacePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        />

        {/* Admin routes */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <AdminDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <ProtectedRoute>
              <AdminUsersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/logs"
          element={
            <ProtectedRoute>
              <AdminLogsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/marketplace"
          element={
            <ProtectedRoute>
              <AdminMarketplacePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/lands"
          element={
            <ProtectedRoute>
              <AdminLandsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/economy"
          element={
            <ProtectedRoute>
              <AdminEconomyPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/moderation"
          element={
            <ProtectedRoute>
              <AdminModerationPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/features"
          element={
            <ProtectedRoute>
              <AdminFeaturesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/communication"
          element={
            <ProtectedRoute>
              <AdminCommunicationPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/security"
          element={
            <ProtectedRoute>
              <AdminSecurityPage />
            </ProtectedRoute>
          }
        />

        {/* Default redirect */}
        <Route
          path="/"
          element={
            <Navigate to={isAuthenticated ? '/world' : '/login'} />
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
