/**
 * Authentication Store
 * Manages user authentication state
 */

import { create } from "zustand";
import { authAPI } from "../services/api";
import { wsService } from "../services/websocket";

const useAuthStore = create((set, get) => ({
  // State
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
  sessionConflict: null, // For handling already-logged-in scenarios

  // Actions
  login: async (email, password) => {
    set({ isLoading: true, error: null, sessionConflict: null });

    try {
      const response = await authAPI.login(email, password);
      const { access_token, refresh_token, user } = response.data;

      // Store tokens
      localStorage.setItem("access_token", access_token);
      localStorage.setItem("refresh_token", refresh_token);

      // Update state
      set({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        sessionConflict: null,
      });

      // Connect WebSocket
      await wsService.connect(access_token);

      return { success: true };
    } catch (error) {
      // Handle session conflict (409)
      if (error.response?.status === 409) {
        const conflictData = error.response?.data?.detail;
        set({
          isLoading: false,
          error: null,
          sessionConflict: conflictData,
        });
        return {
          success: false,
          error: "session_conflict",
          conflict: conflictData,
        };
      }

      const errorMessage = error.response?.data?.detail || "Login failed";
      set({ isLoading: false, error: errorMessage, sessionConflict: null });
      return { success: false, error: errorMessage };
    }
  },

  // Confirm taking over the session (terminate existing session)
  confirmTakeover: async (email, password) => {
    set({ isLoading: true, error: null });

    try {
      const response = await authAPI.confirmTakeover(email, password);
      const { access_token, refresh_token, user } = response.data;

      // Store tokens
      localStorage.setItem("access_token", access_token);
      localStorage.setItem("refresh_token", refresh_token);

      // Update state
      set({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        sessionConflict: null,
      });

      // Connect WebSocket
      await wsService.connect(access_token);

      return { success: true };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || "Takeover failed";
      set({ isLoading: false, error: errorMessage });
      return { success: false, error: errorMessage };
    }
  },

  register: async (username, email, password) => {
    set({ isLoading: true, error: null });

    try {
      await authAPI.register(username, email, password);

      // Auto-login after registration
      return await get().login(email, password);
    } catch (error) {
      const errorMessage =
        error.response?.data?.detail || "Registration failed";
      set({ isLoading: false, error: errorMessage });
      return { success: false, error: errorMessage };
    }
  },

  logout: async () => {
    // Prevent logout during page unload/refresh
    if (window.__isPageUnloading) {
      console.log("Skipping logout - page is unloading");
      return;
    }

    try {
      // Explicitly pass confirm=true to prevent accidental logouts
      await authAPI.logout(true);
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      // Clear tokens
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");

      // Disconnect WebSocket
      wsService.disconnect();

      // Clear state
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        sessionConflict: null,
      });
    }
  },

  loadUser: async () => {
    const token = localStorage.getItem("access_token");

    if (!token) {
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
      return;
    }

    set({ isLoading: true });

    try {
      const response = await authAPI.getMe();
      const user = response.data;

      set({
        user,
        isAuthenticated: true,
        isLoading: false,
      });

      // Connect WebSocket
      await wsService.connect(token);
    } catch (error) {
      console.error("Failed to load user:", error);

      // Don't logout during page unload
      if (window.__isPageUnloading) {
        console.log("Skipping logout on loadUser error - page is unloading");
        return;
      }

      // Only logout if it's a 401 (unauthorized) - network errors shouldn't logout
      if (error.response?.status === 401) {
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        });
        get().logout();
      } else {
        // For other errors, just clear loading state but keep tokens
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        });
      }
    }
  },

  updateUser: (userData) => {
    set((state) => ({
      user: { ...state.user, ...userData },
    }));
  },

  clearError: () => {
    set({ error: null, sessionConflict: null });
  },

  // Prevent logout on page refresh by checking if it's an intentional logout
  preventAccidentalLogout: (shouldLogout = false) => {
    if (!shouldLogout) {
      return; // Do nothing on unintended logouts (e.g., page refresh)
    }
    get().logout();
  },

  // Setup page unload listener to prevent logout on refresh
  setupPageUnloadHandler: () => {
    // Initialize flag to false
    window.__isPageUnloading = false;

    const handleBeforeUnload = () => {
      console.log("beforeunload fired - setting flag");
      window.__isPageUnloading = true;
    };

    const handleVisibilityChange = () => {
      // Reset flag when page becomes visible again
      if (!document.hidden) {
        console.log("Page visible - resetting flag");
        window.__isPageUnloading = false;
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    window.addEventListener("pagehide", handleBeforeUnload);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      window.removeEventListener("pagehide", handleBeforeUnload);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  },
}));

export default useAuthStore;
