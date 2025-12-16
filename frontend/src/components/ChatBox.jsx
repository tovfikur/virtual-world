/**
 * ChatBox Component
 * 3-Mode Chat System:
 * 1. Real-time chat (same square)
 * 2. Leave message for land owner
 * 3. Fenced land restrictions
 */

import { useState, useEffect, useRef } from 'react';
import { wsService } from '../services/websocket';
import { landsAPI, chatAPI } from '../services/api';
import useAuthStore from '../stores/authStore';
import toast from 'react-hot-toast';

function ChatBox({ onClose, land, mode = 'proximity' }) {
  const { user } = useAuthStore();
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [currentRoom, setCurrentRoom] = useState('');
  const [typingUsers, setTypingUsers] = useState(new Set());
  const [canChat, setCanChat] = useState(true);
  const [chatMode, setChatMode] = useState(mode); // 'proximity', 'message', 'restricted'
  const [landOwner, setLandOwner] = useState(null);
  const [roomMembers, setRoomMembers] = useState([]);
  const messagesEndRef = useRef(null);
  const typingTimeoutRef = useRef(null);

  // Initialize chat based on land data
  useEffect(() => {
    const initializeChat = async () => {
      if (!land) {
        setCurrentRoom('global');
        setChatMode('proximity');
        return;
      }

      // Check land ownership and fencing
      const isOwnLand = land.owner_id === user?.user_id;
      const isFenced = land.fenced;
      const hasOwner = Boolean(land.owner_id);

      // Determine chat mode
      if (isFenced && !isOwnLand) {
        // Fenced land - restricted access
        setCanChat(false);
        setChatMode('restricted');
        setLandOwner(land.owner_username || 'Owner');
        toast.error('This land is fenced. Only the owner can receive messages here.');
      } else if (hasOwner && !isOwnLand) {
        // Someone else's land - leave message mode
        setChatMode('message');
        setLandOwner(land.owner_username || 'Owner');
        setCanChat(true);
      } else {
        // Own land or unclaimed - proximity chat mode
        setChatMode('proximity');
        setCanChat(true);

        // If owner is opening their own land, mark messages as read
        if (isOwnLand && land.land_id) {
          try {
            // Try to get the land details to find the chat session
            const response = await landsAPI.getLandByCoords(land.x, land.y);
            const landData = response.data;

            if (landData.land_id) {
              await chatAPI.markSessionAsRead(landData.land_id);
              // Trigger a refresh of unread counts
              window.dispatchEvent(new CustomEvent('unreadMessagesUpdated'));
            }
          } catch (error) {
            console.error('Failed to mark messages as read:', error);
          }
        }
      }

      // Set room name based on coordinates
      const roomName = `land_${land.x}_${land.y}`;
      setCurrentRoom(roomName);
    };

    initializeChat();
  }, [land, user]);

  // Load message history from database
  useEffect(() => {
    const loadMessageHistory = async () => {
      if (!land) {
        console.log('No land selected, skipping history load');
        return;
      }

      console.log(`Loading message history for land (${land.x}, ${land.y})`);

      try {
        // Try to get land details first to get the land_id
        const landResponse = await landsAPI.getLandByCoords(land.x, land.y);
        const landData = landResponse.data;

        console.log('Land data:', landData);

        if (landData.land_id) {
          console.log(`Land has ID: ${landData.land_id}, fetching messages...`);

          // Load message history for this land's chat session
          const messagesResponse = await chatAPI.getLandMessages(landData.land_id, 50);
          const history = messagesResponse.data.messages || [];

          console.log(`✓ Received ${history.length} messages from API:`, history);

          // Set the message history
          const formattedMessages = history.map(msg => ({
            id: msg.message_id,
            sender: msg.sender_username,
            sender_id: msg.sender_id,
            content: msg.content,
            timestamp: new Date(msg.created_at),
            isHistory: true,
            is_leave_message: msg.is_leave_message,
            read_by_owner: msg.read_by_owner
          }));

          setMessages(formattedMessages);
          console.log(`✓ Set ${formattedMessages.length} messages in state`);
        } else {
          // Land not owned yet - no history
          console.log('Land not owned, no history available');
          setMessages([]);
        }
      } catch (error) {
        // If land doesn't have a session yet, that's okay - start fresh
        if (error.response?.status === 404) {
          console.log('No message history for this land yet (404)');
          setMessages([]);
        } else {
          console.error('Failed to load message history:', error);
          setMessages([]);
        }
      }
    };

    loadMessageHistory();
  }, [land]);

  // WebSocket connection and message handling
  useEffect(() => {
    if (!currentRoom) return;

    // Join room
    wsService.joinRoom(currentRoom);

    // Listen for messages
    const unsubscribe = wsService.on('message', (msg) => {
      setMessages((prev) => {
        // Check if message already exists (avoid duplicates)
        const exists = prev.some(m => m.id === msg.message_id);
        if (exists) return prev;

        return [...prev, {
          id: msg.message_id,
          sender: msg.sender_username,
          sender_id: msg.sender_id,
          content: msg.content,
          timestamp: new Date(msg.timestamp),
          isHistory: false,
          is_leave_message: msg.is_leave_message,
          read_by_owner: false  // New messages are unread
        }];
      });
    });

    // Listen for typing indicators
    const unsubscribeTyping = wsService.on('typing', (msg) => {
      if (msg.user_id !== user?.user_id) {
        setTypingUsers((prev) => {
          const newSet = new Set(prev);
          if (msg.is_typing) {
            newSet.add(msg.user_id);
          } else {
            newSet.delete(msg.user_id);
          }
          return newSet;
        });

        // Auto-clear typing indicator after 3 seconds
        setTimeout(() => {
          setTypingUsers((prev) => {
            const newSet = new Set(prev);
            newSet.delete(msg.user_id);
            return newSet;
          });
        }, 3000);
      }
    });

    // Listen for room join confirmation and member updates
    const unsubscribeJoined = wsService.on('joined_room', (msg) => {
      if (msg.room_id === currentRoom) {
        setRoomMembers(msg.members || []);
      }
    });

    // Listen for user joined
    const unsubscribeUserJoined = wsService.on('user_joined', (msg) => {
      if (msg.room_id === currentRoom) {
        setRoomMembers((prev) => {
          if (!prev.includes(msg.user_id)) {
            return [...prev, msg.user_id];
          }
          return prev;
        });
      }
    });

    // Listen for user left
    const unsubscribeUserLeft = wsService.on('user_left', (msg) => {
      if (msg.room_id === currentRoom) {
        setRoomMembers((prev) => prev.filter(id => id !== msg.user_id));
      }
    });

    // Listen for messages cleaned
    const unsubscribeMessagesCleaned = wsService.on('messages_cleaned', (msg) => {
      if (msg.room_id === currentRoom) {
        console.log('Messages cleaned event received:', msg);
        // Clear all messages
        setMessages([]);
        // Trigger refresh of unread counts
        window.dispatchEvent(new CustomEvent('unreadMessagesUpdated'));
        toast.info(`All messages have been cleaned from this square`);
      }
    });

    return () => {
      unsubscribe();
      unsubscribeTyping();
      unsubscribeJoined();
      unsubscribeUserJoined();
      unsubscribeUserLeft();
      unsubscribeMessagesCleaned();
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

  const getChatTitle = () => {
    if (chatMode === 'restricted') {
      return `🔒 Fenced Land - Access Denied`;
    }
    if (chatMode === 'message') {
      return `📬 Leave Message for ${landOwner}`;
    }
    if (land) {
      return `💬 Land Chat (${land.x}, ${land.y})`;
    }
    return `💬 Global Chat`;
  };

  const getChatSubtitle = () => {
    if (chatMode === 'restricted') {
      return `Only ${landOwner} can receive messages here`;
    }
    if (chatMode === 'message') {
      return `Your message will be saved for the owner`;
    }
    if (land) {
      return `Real-time chat with visitors on this land`;
    }
    return `Chat with nearby players`;
  };

  const handleCleanMessages = async () => {
    if (!land || !land.land_id) {
      toast.error('Cannot clean messages: Land not found');
      return;
    }

    // Confirm deletion
    if (!window.confirm('Are you sure you want to delete all messages in this square? This cannot be undone.')) {
      return;
    }

    try {
      const response = await chatAPI.cleanLandMessages(land.land_id);

      // Clear local messages
      setMessages([]);

      // Trigger refresh of unread counts
      window.dispatchEvent(new CustomEvent('unreadMessagesUpdated'));

      toast.success(`Cleaned ${response.data.messages_deleted} messages`);
    } catch (error) {
      console.error('Failed to clean messages:', error);
      toast.error(error.response?.data?.detail || 'Failed to clean messages');
    }
  };

  return (
    <div className="w-full h-80 md:h-96 bg-gray-800 rounded-lg shadow-xl border border-gray-700 flex flex-col">
      {/* Header */}
      <div className={`flex items-center justify-between px-3 md:px-4 py-2 md:py-3 border-b ${chatMode === 'restricted' ? 'bg-red-900/30 border-red-700' : chatMode === 'message' ? 'bg-blue-900/30 border-blue-700' : 'border-gray-700'}`}>
        <div className="flex-1">
          <h3 className="text-white font-semibold text-sm md:text-base">{getChatTitle()}</h3>
          <div className="flex items-center gap-2">
            <p className="text-[10px] md:text-xs text-gray-400">{getChatSubtitle()}</p>
            {roomMembers.length > 0 && chatMode === 'proximity' && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] bg-green-600/30 text-green-300 border border-green-600/50">
                👥 {roomMembers.length} here
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Clean button - show only if there are messages and user has permission */}
          {messages.length > 0 && land?.land_id && (
            <button
              onClick={handleCleanMessages}
              className="text-gray-400 hover:text-red-400 transition-colors"
              title="Clean all messages"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 md:p-4 space-y-2 md:space-y-3">
        {chatMode === 'restricted' ? (
          <div className="text-center text-red-400 mt-8">
            <div className="w-16 h-16 mx-auto mb-4 bg-red-900/50 rounded-full flex items-center justify-center">
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <p className="text-lg font-semibold mb-2">This land is fenced</p>
            <p className="text-sm text-gray-400">Only {landOwner} can receive messages on this land</p>
            <p className="text-xs text-gray-500 mt-3">The owner has restricted access to this property</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="text-center text-gray-500 mt-8">
            {chatMode === 'message' ? (
              <>
                <div className="w-12 h-12 mx-auto mb-3 bg-blue-900/50 rounded-full flex items-center justify-center">
                  <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </div>
                <p>No messages yet</p>
                <p className="text-sm mt-1">Leave a message for {landOwner}</p>
              </>
            ) : (
              <>
                <p>No messages yet</p>
                <p className="text-sm mt-1">Start chatting with visitors on this land!</p>
              </>
            )}
          </div>
        ) : (
          messages.map((msg) => {
            const isMine = msg.sender_id === user?.user_id;

            return (
              <div key={msg.id} className="animate-slideUp">
                <div className={`flex items-start space-x-2 ${isMine ? 'flex-row-reverse space-x-reverse' : ''}`}>
                  <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-semibold ${isMine ? 'bg-green-600' : 'bg-blue-600'}`}>
                    {msg.sender[0].toUpperCase()}
                  </div>
                  <div className="flex-1">
                    <div className={`flex items-baseline space-x-2 ${isMine ? 'flex-row-reverse space-x-reverse' : ''}`}>
                      <span className="text-white font-semibold text-sm">{msg.sender}</span>
                      <span className="text-gray-500 text-xs">
                        {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                    <div className={`flex items-end gap-1 ${isMine ? 'flex-row-reverse' : ''}`}>
                      <p className={`text-gray-300 text-sm mt-1 break-words ${isMine ? 'text-right' : ''}`}>{msg.content}</p>
                      {isMine && msg.is_leave_message && (
                        <div className="flex-shrink-0 mb-1" title={msg.read_by_owner ? "Read" : "Delivered"}>
                          {msg.read_by_owner ? (
                            // Double checkmark (blue) - Read
                            <svg className="w-4 h-4 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M0 11l2-2 5 5L18 3l2 2L7 18z"/>
                              <path d="M0 11l2-2 5 5L18 3l2 2L7 18z" transform="translate(3, 0)"/>
                            </svg>
                          ) : (
                            // Double checkmark (gray) - Delivered but not read
                            <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M0 11l2-2 5 5L18 3l2 2L7 18z"/>
                              <path d="M0 11l2-2 5 5L18 3l2 2L7 18z" transform="translate(3, 0)"/>
                            </svg>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
        {typingUsers.size > 0 && canChat && (
          <div className="text-gray-500 text-sm italic">
            {typingUsers.size === 1 ? 'Someone is' : `${typingUsers.size} people are`} typing...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSendMessage} className="p-2 md:p-4 border-t border-gray-700">
        {canChat ? (
          <div className="flex space-x-2">
            <input
              type="text"
              value={inputValue}
              onChange={handleInputChange}
              placeholder={chatMode === 'message' ? `Leave a message for ${landOwner}...` : "Type a message..."}
              className="flex-1 px-2 md:px-3 py-2 bg-gray-700 text-white rounded-lg border border-gray-600 focus:border-blue-500 focus:outline-none text-xs md:text-sm"
              maxLength={500}
            />
            <button
              type="submit"
              className={`px-3 md:px-4 py-2 ${chatMode === 'message' ? 'bg-green-600 hover:bg-green-700' : 'bg-blue-600 hover:bg-blue-700'} text-white rounded-lg transition-colors`}
              title={chatMode === 'message' ? 'Send message to owner' : 'Send message'}
            >
              <svg className="w-4 h-4 md:w-5 md:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        ) : (
          <div className="text-center py-3 bg-red-900/20 rounded-lg border border-red-700">
            <p className="text-red-400 text-sm font-semibold">🔒 Chat Disabled</p>
            <p className="text-xs text-gray-400 mt-1">This fenced land is private</p>
          </div>
        )}
      </form>
    </div>
  );
}

export default ChatBox;
