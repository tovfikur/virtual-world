/**
 * ChatBox Component
 * Real-time chat with WebSocket integration
 */

import { useState, useEffect, useRef } from 'react';
import { wsService } from '../services/websocket';
import useAuthStore from '../stores/authStore';

function ChatBox({ onClose }) {
  const { user } = useAuthStore();
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [currentRoom, setCurrentRoom] = useState('global');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const typingTimeoutRef = useRef(null);

  useEffect(() => {
    // Join global room
    wsService.joinRoom(currentRoom);

    // Listen for messages
    const unsubscribe = wsService.on('message', (msg) => {
      setMessages((prev) => [...prev, {
        id: msg.message_id,
        sender: msg.sender_username,
        content: msg.content,
        timestamp: new Date(msg.timestamp),
      }]);
    });

    // Listen for typing indicators
    const unsubscribeTyping = wsService.on('typing', (msg) => {
      if (msg.user_id !== user.user_id) {
        setIsTyping(msg.is_typing);
      }
    });

    return () => {
      unsubscribe();
      unsubscribeTyping();
      wsService.leaveRoom(currentRoom);
    };
  }, [currentRoom, user]);

  useEffect(() => {
    // Auto-scroll to bottom
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = (e) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    wsService.sendMessage(currentRoom, inputValue);
    setInputValue('');

    // Stop typing indicator
    wsService.sendTyping(currentRoom, false);
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
  };

  const handleInputChange = (e) => {
    setInputValue(e.target.value);

    // Send typing indicator
    wsService.sendTyping(currentRoom, true);

    // Clear previous timeout
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    // Stop typing after 2 seconds of inactivity
    typingTimeoutRef.current = setTimeout(() => {
      wsService.sendTyping(currentRoom, false);
    }, 2000);
  };

  return (
    <div className="w-full sm:w-96 h-96 bg-gray-800 rounded-lg shadow-xl border border-gray-700 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
        <div>
          <h3 className="text-white font-semibold">Chat</h3>
          <p className="text-xs text-gray-400">Room: {currentRoom}</p>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 mt-8">
            <p>No messages yet</p>
            <p className="text-sm mt-1">Start chatting with nearby players!</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className="animate-slideUp">
              <div className="flex items-start space-x-2">
                <div className="flex-shrink-0 w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white text-sm font-semibold">
                  {msg.sender[0].toUpperCase()}
                </div>
                <div className="flex-1">
                  <div className="flex items-baseline space-x-2">
                    <span className="text-white font-semibold text-sm">{msg.sender}</span>
                    <span className="text-gray-500 text-xs">
                      {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <p className="text-gray-300 text-sm mt-1 break-words">{msg.content}</p>
                </div>
              </div>
            </div>
          ))
        )}
        {isTyping && (
          <div className="text-gray-500 text-sm italic">Someone is typing...</div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSendMessage} className="p-4 border-t border-gray-700">
        <div className="flex space-x-2">
          <input
            type="text"
            value={inputValue}
            onChange={handleInputChange}
            placeholder="Type a message..."
            className="flex-1 px-3 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none text-sm"
            maxLength={500}
          />
          <button
            type="submit"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
}

export default ChatBox;
