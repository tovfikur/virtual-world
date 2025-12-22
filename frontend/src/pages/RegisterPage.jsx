/**
 * Register Page
 * User registration form with validation
 */

import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import useAuthStore from "../stores/authStore";

function RegisterPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const { register, isLoading, error, clearError } = useAuthStore();
  const navigate = useNavigate();

  // Clear error when user starts typing
  useEffect(() => {
    clearError();
  }, [username, email, password, confirmPassword, clearError]);

  const validatePassword = () => {
    if (password.length < 6) {
      return "Password must be at least 6 characters";
    }
    return null;
  };

  const passwordsMatch = password.length > 0 && password === confirmPassword;
  const passwordsMismatch =
    password.length > 0 &&
    confirmPassword.length > 0 &&
    password !== confirmPassword;

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Trim whitespace for comparison
    const trimmedPassword = password.trim();
    const trimmedConfirmPassword = confirmPassword.trim();

    // Validation
    if (trimmedPassword !== trimmedConfirmPassword) {
      toast.error("Passwords do not match");
      return;
    }

    if (trimmedPassword.length < 6) {
      toast.error("Password must be at least 6 characters");
      return;
    }

    if (!username.trim()) {
      toast.error("Username is required");
      return;
    }

    if (!email.trim()) {
      toast.error("Email is required");
      return;
    }

    const result = await register(
      username.trim(),
      email.trim(),
      trimmedPassword
    );

    if (result.success) {
      toast.success("Account created! Welcome to Virtual Land World!");
      navigate("/world");
    } else {
      toast.error(result.error || "Registration failed");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            Virtual Land World
          </h1>
          <p className="text-gray-400">
            Create your account and claim your first land
          </p>
        </div>

        <div className="bg-gray-800 rounded-lg shadow-xl p-8 border border-gray-700">
          <h2 className="text-2xl font-bold text-white mb-6">Sign Up</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none"
                placeholder="Choose a username"
                required
                minLength={3}
                maxLength={20}
              />
            </div>

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
                placeholder="At least 6 characters"
                required
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-300">
                  Confirm Password
                </label>
                {confirmPassword.length > 0 && (
                  <span className="text-xs font-medium">
                    {passwordsMatch ? (
                      <span className="text-green-400 flex items-center gap-1">
                        <span>✓</span> Match
                      </span>
                    ) : (
                      <span className="text-red-400 flex items-center gap-1">
                        <span>✗</span> No Match
                      </span>
                    )}
                  </span>
                )}
              </div>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={`w-full px-4 py-2 bg-gray-700 text-white rounded-lg border focus:outline-none transition-colors ${
                  confirmPassword.length === 0
                    ? "border-gray-600 focus:border-blue-500"
                    : passwordsMatch
                    ? "border-green-500 focus:border-green-400"
                    : "border-red-500 focus:border-red-400"
                }`}
                placeholder="Confirm your password"
                required
              />
            </div>

            {error && (
              <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            <div className="bg-blue-900/30 border border-blue-700 text-blue-200 px-4 py-3 rounded-lg text-sm">
              <p className="font-semibold mb-1">Password Requirements:</p>
              <ul className="list-disc list-inside space-y-1">
                <li>At least 6 characters</li>
              </ul>
            </div>

            <button
              type="submit"
              disabled={
                isLoading || (confirmPassword.length > 0 && !passwordsMatch)
              }
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-semibold py-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title={
                confirmPassword.length > 0 && !passwordsMatch
                  ? "Passwords must match"
                  : ""
              }
            >
              {isLoading ? "Creating account..." : "Create Account"}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-gray-400">
              Already have an account?{" "}
              <Link
                to="/login"
                className="text-blue-400 hover:text-blue-300 font-medium"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>

        <div className="mt-8 text-center text-gray-500 text-sm">
          <p>By signing up, you agree to our Terms of Service</p>
        </div>
      </div>
    </div>
  );
}

export default RegisterPage;
