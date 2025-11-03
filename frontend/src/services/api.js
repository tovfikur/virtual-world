/**
 * API Service
 * Handles all HTTP requests to the backend
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds for chunk generation
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Handle 401 Unauthorized
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Try to refresh token
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });

          const { access_token } = response.data;
          localStorage.setItem('access_token', access_token);

          // Retry original request
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, logout user
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// ============================================
// Authentication
// ============================================

export const authAPI = {
  register: (username, email, password) =>
    api.post('/auth/register', { username, email, password }),

  login: (email, password) =>
    api.post('/auth/login', { email, password }),

  logout: () =>
    api.post('/auth/logout'),

  getMe: () =>
    api.get('/auth/me'),

  refresh: (refreshToken) =>
    api.post('/auth/refresh', { refresh_token: refreshToken }),
};

// ============================================
// Users
// ============================================

export const usersAPI = {
  getUser: (userId) =>
    api.get(`/users/${userId}`),

  updateUser: (userId, data) =>
    api.put(`/users/${userId}`, data),

  getBalance: (userId) =>
    api.get(`/users/${userId}/balance`),

  initiateTopup: (userId, amountBdt, gateway) =>
    api.post(`/users/${userId}/topup`, null, {
      params: { amount_bdt: amountBdt, gateway },
    }),

  getUserLands: (userId, page = 1, limit = 20) =>
    api.get(`/users/${userId}/lands`, { params: { page, limit } }),

  getUserStats: (userId) =>
    api.get(`/users/${userId}/stats`),
};

// ============================================
// Lands
// ============================================

export const landsAPI = {
  getLand: (landId) =>
    api.get(`/lands/${landId}`),

  searchLands: (params) =>
    api.get('/lands', { params }),

  updateLand: (landId, data) =>
    api.put(`/lands/${landId}`, data),

  manageFence: (landId, fenced, passcode) =>
    api.post(`/lands/${landId}/fence`, { fenced, passcode }),

  transferLand: (landId, newOwnerId, message) =>
    api.post(`/lands/${landId}/transfer`, {
      new_owner_id: newOwnerId,
      message,
    }),

  getLandHeatmap: (landId, radius = 10) =>
    api.get(`/lands/${landId}/heatmap`, { params: { radius } }),
};

// ============================================
// Chunks (World Generation)
// ============================================

export const chunksAPI = {
  getChunk: (chunkX, chunkY, chunkSize = 32) =>
    api.get(`/chunks/${chunkX}/${chunkY}`, { params: { chunk_size: chunkSize } }),

  getChunksBatch: (chunks, chunkSize = 32) =>
    api.post('/chunks/batch', chunks, { params: { chunk_size: chunkSize } }),

  getLandAt: (x, y) =>
    api.get(`/chunks/land/${x}/${y}`),

  getChunkPreview: (chunkX, chunkY, chunkSize = 32) =>
    api.get(`/chunks/preview/${chunkX}/${chunkY}`, { params: { chunk_size: chunkSize } }),

  getWorldInfo: () =>
    api.get('/chunks/info'),
};

// ============================================
// Marketplace
// ============================================

export const marketplaceAPI = {
  createListing: (data) =>
    api.post('/marketplace/listings', data),

  getListings: (params) =>
    api.get('/marketplace/listings', { params }),

  getListing: (listingId) =>
    api.get(`/marketplace/listings/${listingId}`),

  placeBid: (listingId, amountBdt) =>
    api.post(`/marketplace/listings/${listingId}/bids`, { amount_bdt: amountBdt }),

  getListingBids: (listingId, page = 1, limit = 20) =>
    api.get(`/marketplace/listings/${listingId}/bids`, { params: { page, limit } }),

  buyNow: (listingId, paymentMethod = 'balance') =>
    api.post(`/marketplace/listings/${listingId}/buy-now`, { payment_method: paymentMethod }),

  cancelListing: (listingId) =>
    api.delete(`/marketplace/listings/${listingId}`),

  getRichestLeaderboard: (limit = 100) =>
    api.get('/marketplace/leaderboard/richest', { params: { limit } }),

  getLandownersLeaderboard: (limit = 100) =>
    api.get('/marketplace/leaderboard/landowners', { params: { limit } }),
};

// ============================================
// Chat
// ============================================

export const chatAPI = {
  getSessions: () =>
    api.get('/chat/sessions'),

  getMessages: (sessionId, limit = 50, beforeMessageId = null) =>
    api.get(`/chat/sessions/${sessionId}/messages`, {
      params: { limit, before_message_id: beforeMessageId },
    }),

  sendMessage: (sessionId, content) =>
    api.post(`/chat/sessions/${sessionId}/messages`, null, {
      params: { content },
    }),

  deleteMessage: (sessionId, messageId) =>
    api.delete(`/chat/sessions/${sessionId}/messages/${messageId}`),

  getLandParticipants: (landId, radius = 5) =>
    api.get(`/chat/land/${landId}/participants`, { params: { radius } }),

  createLandSession: (landId) =>
    api.post(`/chat/land/${landId}/session`),

  getChatStats: () =>
    api.get('/chat/stats'),
};

// ============================================
// WebSocket Stats
// ============================================

export const wsAPI = {
  getStats: () =>
    api.get('/ws/stats'),

  getOnlineUsers: () =>
    api.get('/ws/online-users'),

  getActiveCalls: () =>
    api.get('/webrtc/active-calls'),
};

// ============================================
// Health Check
// ============================================

export const healthAPI = {
  check: () =>
    axios.get(`${API_BASE_URL.replace('/api/v1', '')}/health`),
};

// ============================================
// Admin
// ============================================

export const adminAPI = {
  // Dashboard
  getDashboardStats: () =>
    api.get('/admin/dashboard/stats'),

  getRevenueAnalytics: (days = 30) =>
    api.get('/admin/analytics/revenue', { params: { days } }),

  getUserAnalytics: (days = 30) =>
    api.get('/admin/analytics/users', { params: { days } }),

  // User Management
  listUsers: (params) =>
    api.get('/admin/users', { params }),

  getUserDetails: (userId) =>
    api.get(`/admin/users/${userId}`),

  updateUser: (userId, data) =>
    api.patch(`/admin/users/${userId}`, data),

  // System Monitoring
  getSystemHealth: () =>
    api.get('/admin/system/health'),

  getAuditLogs: (params) =>
    api.get('/admin/system/audit-logs', { params }),

  // World Configuration
  getWorldConfig: () =>
    api.get('/admin/config/world'),

  updateWorldConfig: (data) =>
    api.patch('/admin/config/world', data),
};

export default api;
