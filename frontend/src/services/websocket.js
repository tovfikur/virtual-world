/**
 * WebSocket Service
 * Handles real-time communication with the server
 */

class WebSocketService {
  constructor() {
    this.ws = null;
    this.isConnected = false;
    this.listeners = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.heartbeatInterval = null;
  }

  connect(token) {
    const envWsUrl = import.meta.env.VITE_WS_URL;
    const defaultWsUrl = `${window.location.protocol === 'https:' ? 'wss://' : 'ws://'}${window.location.host}`;
    const wsUrl = envWsUrl && envWsUrl.trim() !== '' ? envWsUrl : defaultWsUrl;
    const url = `${wsUrl.replace(/\/?$/, '')}/api/v1/ws/connect?token=${token}`;

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.startHeartbeat();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          reject(error);
        };

        this.ws.onclose = () => {
          console.log('WebSocket disconnected');
          this.isConnected = false;
          this.stopHeartbeat();
          this.attemptReconnect(token);
        };
      } catch (error) {
        console.error('Failed to create WebSocket:', error);
        reject(error);
      }
    });
  }

  disconnect() {
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
  }

  send(type, data = {}) {
    if (!this.isConnected || !this.ws) {
      console.warn('WebSocket not connected');
      return false;
    }

    try {
      const message = JSON.stringify({ type, ...data });
      this.ws.send(message);
      return true;
    } catch (error) {
      console.error('Failed to send WebSocket message:', error);
      return false;
    }
  }

  // Message handlers
  handleMessage(message) {
    const { type } = message;

    // Emit to specific listeners
    if (this.listeners.has(type)) {
      this.listeners.get(type).forEach((callback) => callback(message));
    }

    // Emit to global listeners
    if (this.listeners.has('*')) {
      this.listeners.get('*').forEach((callback) => callback(message));
    }
  }

  on(messageType, callback) {
    if (!this.listeners.has(messageType)) {
      this.listeners.set(messageType, new Set());
    }
    this.listeners.get(messageType).add(callback);

    // Return unsubscribe function
    return () => {
      const callbacks = this.listeners.get(messageType);
      if (callbacks) {
        callbacks.delete(callback);
      }
    };
  }

  off(messageType, callback) {
    const callbacks = this.listeners.get(messageType);
    if (callbacks) {
      callbacks.delete(callback);
    }
  }

  // Room management
  joinRoom(roomId) {
    return this.send('join_room', { room_id: roomId });
  }

  leaveRoom(roomId) {
    return this.send('leave_room', { room_id: roomId });
  }

  // Chat
  sendMessage(roomId, content) {
    return this.send('send_message', {
      room_id: roomId,
      content,
    });
  }

  sendTyping(roomId, isTyping = true) {
    return this.send('typing', {
      room_id: roomId,
      is_typing: isTyping,
    });
  }

  // Location
  updateLocation(x, y) {
    return this.send('update_location', { x, y });
  }

  // Heartbeat
  startHeartbeat() {
    this.heartbeatInterval = setInterval(() => {
      this.send('ping');
    }, 30000); // Every 30 seconds
  }

  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  // Reconnection
  attemptReconnect(token) {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      this.connect(token).catch((error) => {
        console.error('Reconnection failed:', error);
      });
    }, delay);
  }
}

// Global instance
export const wsService = new WebSocketService();
export default wsService;
