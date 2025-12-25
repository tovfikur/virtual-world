/**
 * Authentication Store
 * Manages user authentication state
 */

import { create } from 'zustand';
import { authAPI } from '../services/api';
import { wsService } from '../services/websocket';

const useAuthStore = create((set, get) => ({
  // State
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  // Actions
  login: async (email, password) => {
    set({ isLoading: true, error: null });

    try {
      const response = await authAPI.login(email, password);
      const { access_token, refresh_token, user } = response.data;

      // Store tokens
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

      // Update state
      set({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });

      // Connect WebSocket
      await wsService.connect(access_token);

      return { success: true };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Login failed';
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
      const errorMessage = error.response?.data?.detail || 'Registration failed';
      set({ isLoading: false, error: errorMessage });
      return { success: false, error: errorMessage };
    }
  },

  logout: async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear tokens
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');

      // Disconnect WebSocket
      wsService.disconnect();

      // Clear state
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  },

  loadUser: async () => {
    const token = localStorage.getItem('access_token');

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
      console.error('Failed to load user:', error);
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
      get().logout();
    }
  },

  updateUser: (userData) => {
    set((state) => ({
      user: { ...state.user, ...userData },
    }));
  },

  clearError: () => {
    set({ error: null });
  },
}));

export default useAuthStore;
