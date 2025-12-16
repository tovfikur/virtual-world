/**
 * API Service
 * Handles all HTTP requests to the backend
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || `${window.location.origin}/api/v1`;

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

  getLandByCoords: (x, y) =>
    api.get(`/lands/coordinates/${x}/${y}`),

  getOwnerCoordinates: (ownerId, limit = 5000) =>
    api.get(`/lands/owner/${ownerId}/coordinates`, { params: { limit } }),

  searchLands: (params) =>
    api.get('/lands', { params }),

  claimLand: (data) =>
    api.post('/lands/claim', data),

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

  getUnreadMessages: () =>
    api.get('/chat/unread-messages'),

  markSessionAsRead: (sessionId) =>
    api.post(`/chat/sessions/${sessionId}/mark-read`),

  getLandMessages: (landId, limit = 50) =>
    api.get(`/chat/land/${landId}/messages`, { params: { limit } }),

  cleanLandMessages: (landId) =>
    api.delete(`/chat/land/${landId}/messages`),
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

  // Marketplace & Economy
  getMarketplaceListings: (params) =>
    api.get('/admin/marketplace/listings', { params }),

  removeListing: (listingId, reason) =>
    api.delete(`/admin/marketplace/listings/${listingId}`, { params: { reason } }),

  getTransactions: (params) =>
    api.get('/admin/transactions', { params }),

  refundTransaction: (transactionId, reason) =>
    api.post(`/admin/transactions/${transactionId}/refund`, null, { params: { reason } }),

  exportTransactions: (startDate, endDate) =>
    api.get('/admin/transactions/export', { params: { start_date: startDate, end_date: endDate } }),

  getEconomicSettings: () =>
    api.get('/admin/config/economy'),

  updateEconomicSettings: (data) =>
    api.patch('/admin/config/economy', data),

  // Land Management
  getLandAnalytics: () =>
    api.get('/admin/lands/analytics'),

  transferLand: (landId, newOwnerId, reason) =>
    api.post(`/admin/lands/${landId}/transfer`, null, { params: { new_owner_id: newOwnerId, reason } }),

  reclaimLand: (landId, reason) =>
    api.delete(`/admin/lands/${landId}/reclaim`, { params: { reason } }),

  // User Management Extended
  suspendUser: (userId, data) =>
    api.post(`/admin/users/${userId}/suspend`, data),

  unsuspendUser: (userId) =>
    api.post(`/admin/users/${userId}/unsuspend`),

  banUser: (userId, data) =>
    api.post(`/admin/users/${userId}/ban`, data),

  unbanUser: (userId) =>
    api.delete(`/admin/users/${userId}/ban`),

  getUserActivity: (userId) =>
    api.get(`/admin/users/${userId}/activity`),

  // Configuration
  getFeatureToggles: () =>
    api.get('/admin/config/features'),

  updateFeatureToggles: (data) =>
    api.patch('/admin/config/features', data),

  getSystemLimits: () =>
    api.get('/admin/config/limits'),

  updateSystemLimits: (data) =>
    api.patch('/admin/config/limits', data),

  // Content Moderation
  getChatMessages: (params) =>
    api.get('/admin/moderation/chat-messages', { params }),

  deleteMessage: (messageId, reason) =>
    api.delete(`/admin/moderation/messages/${messageId}`, { params: { reason } }),

  muteUser: (userId, data, reason) =>
    api.post(`/admin/moderation/users/${userId}/mute`, data, { params: { reason } }),

  getReports: (params) =>
    api.get('/admin/moderation/reports', { params }),

  resolveReport: (reportId, data) =>
    api.patch(`/admin/moderation/reports/${reportId}`, data),

  // Communication
  getAnnouncements: (params) =>
    api.get('/admin/announcements', { params }),

  createAnnouncement: (data) =>
    api.post('/admin/announcements', data),

  updateAnnouncement: (announcementId, data) =>
    api.patch(`/admin/announcements/${announcementId}`, data),

  deleteAnnouncement: (announcementId) =>
    api.delete(`/admin/announcements/${announcementId}`),

  sendBroadcast: (data) =>
    api.post('/admin/broadcast', data),

  // Security
  getAllBans: (params) =>
    api.get('/admin/security/bans', { params }),

  getSecurityLogs: (params) =>
    api.get('/admin/security/logs', { params }),
};

export default api;
