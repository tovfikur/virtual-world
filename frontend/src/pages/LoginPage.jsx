/**
 * Login Page
 * User login form
 */

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import useAuthStore from "../stores/authStore";

function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isConfirmingTakeover, setIsConfirmingTakeover] = useState(false);
  const { login, confirmTakeover, isLoading, error, sessionConflict } =
    useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();

    const result = await login(email, password);

    if (result.success) {
      toast.success("Welcome back!");
      navigate("/world");
    } else if (result.error !== "session_conflict") {
      toast.error(result.error || "Login failed");
    }
    // For session_conflict, the conflict dialog will be shown below
  };

  const handleConfirmTakeover = async () => {
    setIsConfirmingTakeover(true);
    const result = await confirmTakeover(email, password);
    setIsConfirmingTakeover(false);

    if (result.success) {
      toast.success("Session taken over. Welcome!");
      navigate("/world");
    } else {
      toast.error(result.error || "Failed to take over session");
    }
  };

  const handleLogoutOtherSession = () => {
    toast("Please logout from your other device to login here", {
      icon: "ℹ️",
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        {/* Session Conflict Dialog */}
        {sessionConflict && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <div className="bg-gray-800 rounded-lg shadow-2xl p-8 border border-yellow-600 max-w-md w-full">
              <h2 className="text-2xl font-bold text-yellow-400 mb-4">
                ⚠️ Account Already Logged In
              </h2>

              <div className="bg-gray-900 rounded p-4 mb-6 space-y-2 text-gray-300 text-sm">
                <p>
                  <span className="text-gray-400">Device:</span>{" "}
                  <span className="text-white">
                    {sessionConflict.active_session_device}
                  </span>
                </p>
                <p>
                  <span className="text-gray-400">IP Address:</span>{" "}
                  <span className="text-white">
                    {sessionConflict.active_session_ip}
                  </span>
                </p>
                <p>
                  <span className="text-gray-400">Started:</span>{" "}
                  <span className="text-white">
                    {new Date(
                      sessionConflict.active_session_started
                    ).toLocaleString()}
                  </span>
                </p>
              </div>

              <p className="text-gray-300 mb-6">
                Your account is already logged in from another device. Choose an
                action below:
              </p>

              <div className="space-y-3">
                <button
                  onClick={handleConfirmTakeover}
                  disabled={isConfirmingTakeover || isLoading}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isConfirmingTakeover
                    ? "Taking Over..."
                    : "Login on This Device"}
                </button>

                <button
                  onClick={handleLogoutOtherSession}
                  disabled={isLoading}
                  className="w-full bg-gray-700 hover:bg-gray-600 text-white font-semibold py-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Logout From Other Device
                </button>
              </div>

              <p className="text-xs text-gray-400 mt-4 text-center">
                This security feature prevents unauthorized access to your
                account
              </p>
            </div>
          </div>
        )}

        {/* Normal Login Form */}
        {!sessionConflict && (
          <>
            <div className="text-center mb-8">
              <h1 className="text-4xl font-bold text-white mb-2">
                Virtual Land World
              </h1>
              <p className="text-gray-400">
                Own, trade, and explore virtual land
              </p>
            </div>

            <div className="bg-gray-800 rounded-lg shadow-xl p-8 border border-gray-700">
              <h2 className="text-2xl font-bold text-white mb-6">Sign In</h2>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
                    placeholder="your@email.com"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Password
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
                    placeholder="••••••••"
                    required
                  />
                </div>

                {error && (
                  <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded-lg">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? "Signing in..." : "Sign In"}
                </button>
              </form>

              <div className="mt-6 text-center">
                <p className="text-gray-400">
                  Don't have an account?{" "}
                  <Link
                    to="/register"
                    className="text-blue-400 hover:text-blue-300 font-medium"
                  >
                    Sign up
                  </Link>
                </p>
              </div>
            </div>

            <div className="mt-8 text-center text-gray-500 text-sm">
              <p>Demo Credentials:</p>
              <p>Email: demo@example.com</p>
              <p>Password: DemoPassword123!</p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default LoginPage;
