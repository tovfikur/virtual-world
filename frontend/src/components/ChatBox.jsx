/**
 * ChatBox Component
 * 3-Mode Chat System:
 * 1. Real-time chat (same square)
 * 2. Leave message for land owner
 * 3. Fenced land restrictions
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { wsService } from '../services/websocket';
import { landsAPI, chatAPI, wsAPI, usersAPI } from '../services/api';
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
  const [coLocatedUsers, setCoLocatedUsers] = useState([]);
  const [memberNames, setMemberNames] = useState({});
  const [restrictionReason, setRestrictionReason] = useState(null);
  const [accessEntries, setAccessEntries] = useState([]);
  const [accessRestricted, setAccessRestricted] = useState(false);
  const [showAccessPanel, setShowAccessPanel] = useState(false);
  const [accessSearchTerm, setAccessSearchTerm] = useState('');
  const [accessSearchResults, setAccessSearchResults] = useState([]);
  const [accessLoading, setAccessLoading] = useState(false);
  const [accessSaving, setAccessSaving] = useState(false);
  const [applyToAllFenced, setApplyToAllFenced] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const messagesEndRef = useRef(null);
  const typingTimeoutRef = useRef(null);
  const memberNamesRef = useRef({});
  const markReadPendingRef = useRef(false);
  const isOwnLand = land?.owner_id === user?.user_id;

  const rememberMemberNames = useCallback((updates) => {
    if (!updates || Object.keys(updates).length === 0) return;
    memberNamesRef.current = { ...memberNamesRef.current, ...updates };
    setMemberNames(memberNamesRef.current);
  }, []);

  const resolveMemberNames = useCallback(
    async (userIds) => {
      const uniqueIds = Array.from(
        new Set(userIds.filter((id) => id && !memberNamesRef.current[id]))
      );
      if (uniqueIds.length === 0) {
        return;
      }
      try {
        const onlineResponse = await wsAPI.getOnlineUsers();
        const collected = {};
        onlineResponse.data?.users?.forEach((onlineUser) => {
          if (uniqueIds.includes(onlineUser.user_id)) {
            collected[onlineUser.user_id] =
              onlineUser.username || onlineUser.email || "Visitor";
          }
        });

        const unresolved = uniqueIds.filter((id) => !collected[id]);
        if (unresolved.length > 0) {
          const fetched = await Promise.all(
            unresolved.map(async (id) => {
              try {
                const response = await usersAPI.getUser(id);
                const username =
                  response.data?.username ||
                  response.data?.email ||
                  response.data?.user_id?.slice(0, 6) ||
                  "Visitor";
                return { id, username };
              } catch (error) {
                console.error(`Failed to load user ${id}`, error);
                return { id, username: "Visitor" };
              }
            })
          );
          fetched.forEach(({ id, username }) => {
            collected[id] = username;
          });
        }

        if (Object.keys(collected).length > 0) {
          rememberMemberNames(collected);
        }
      } catch (error) {
        console.error("Failed to resolve member names", error);
      }
    },
    [rememberMemberNames]
  );

  const loadAccessEntries = useCallback(async () => {
    if (!land?.land_id || !isOwnLand || !land?.fenced) {
      setAccessEntries([]);
      setAccessRestricted(false);
      return;
    }
    try {
      const response = await landsAPI.getChatAccessList(land.land_id);
      const data = response.data || {};
      setAccessEntries(data.entries || []);
      setAccessRestricted(Boolean(data.restricted));
    } catch (error) {
      console.error('Failed to load chat access list', error);
    }
  }, [land?.land_id, land?.fenced, isOwnLand]);

  const otherMemberNames = useMemo(() => {
    const seen = new Set();
    const participantIds = [
      ...roomMembers,
      ...coLocatedUsers.map((p) => p.user_id),
    ];
    return participantIds
      .filter((id) => id && id !== user?.user_id)
      .map((id) => memberNamesRef.current[id] || memberNames[id] || 'Visitor')
      .filter((name) => {
        if (seen.has(name)) {
          return false;
        }
        seen.add(name);
        return true;
      });
  }, [roomMembers, memberNames, user?.user_id]);

  const presenceTitle = useMemo(() => {
    if (chatMode === 'restricted') return null;
    if (otherMemberNames.length === 0) return null;
    if (otherMemberNames.length === 1) {
      const baseName = otherMemberNames[0];
      return messages.length > 0 ? baseName : `${baseName} is here`;
    }
    if (otherMemberNames.length === 2) {
      return `${otherMemberNames[0]} & ${otherMemberNames[1]} are here`;
    }
    return `${otherMemberNames.length} people are chatting here`;
  }, [chatMode, otherMemberNames, messages.length]);

  const presenceSubtitle = useMemo(() => {
    if (!presenceTitle) return null;
    if (otherMemberNames.length > 2) {
      return `${otherMemberNames.length} visitors are active on this land`;
    }
    if (otherMemberNames.length === 2) {
      return 'Group chat in progress';
    }
    return 'Real-time chat is available right now';
  }, [otherMemberNames.length, presenceTitle]);

  useEffect(() => {
    loadAccessEntries();
  }, [loadAccessEntries]);

  useEffect(() => {
    if (!land?.fenced) {
      setShowAccessPanel(false);
    }
  }, [land?.fenced]);

  const markMessagesAsRead = useCallback(
    async (explicitSessionId = null) => {
      if (!isOwnLand) {
        return;
      }
      const sessionIdToUse = explicitSessionId || currentSessionId;
      if (!sessionIdToUse || markReadPendingRef.current) {
        return;
      }
      markReadPendingRef.current = true;
      try {
        await chatAPI.markSessionAsRead(sessionIdToUse);
        window.dispatchEvent(new CustomEvent('unreadMessagesUpdated'));
      } catch (error) {
        console.error('Failed to mark messages as read:', error);
      } finally {
        markReadPendingRef.current = false;
      }
    },
    [currentSessionId, isOwnLand]
  );

  // Initialize chat based on land data
  useEffect(() => {
    const initializeChat = async () => {
      setRestrictionReason(null);
      setCanChat(true);

      if (!land) {
        setCurrentRoom('global');
        setChatMode('proximity');
        setLandOwner(null);
        return;
      }

      // Check land ownership
      const ownsLand = land.owner_id === user?.user_id;
      const isFenced = Boolean(land.fenced);
      const hasOwner = Boolean(land.owner_id);
      const ownerLabel = land.owner_username || 'Owner';
      if (hasOwner) {
        setLandOwner(ownerLabel);
      } else {
        setLandOwner(null);
      }

      // Determine chat mode
      if (isFenced && !ownsLand) {
        setChatMode('restricted');
        setCanChat(false);
        setRestrictionReason('This fenced land only allows invited guests.');
      } else if (hasOwner && !ownsLand) {
        // Someone else's land - leave message mode
        setChatMode('message');
        setCanChat(true);
      } else {
        // Own land or unclaimed - proximity chat mode
        setChatMode('proximity');
        setCanChat(true);
      }

      // Set room name based on coordinates
      const roomName = `land_${land.x}_${land.y}`;
      setCurrentRoom(roomName);
    };

    initializeChat();
  }, [land, user]);

  // Load message history from database
  useEffect(() => {
    let cancelled = false;

    const loadMessageHistory = async () => {
      let ownsLand = land?.owner_id === user?.user_id;
      let isFencedVisitor = Boolean(land?.fenced) && !ownsLand;
      let hasOwner = Boolean(land?.owner_id);

      if (!land) {
        setRestrictionReason(null);
        setCanChat(true);
        setMessages([]);
        setChatMode('proximity');
        setCurrentSessionId(null);
        return;
      }

      try {
        const landResponse = await landsAPI.getLandByCoords(land.x, land.y);
        if (cancelled) {
          return;
        }
        const landData = landResponse.data || {};
        const resolvedLandId = landData.land_id || land.land_id;
        const resolvedOwnerId =
          landData.owner_id !== undefined ? landData.owner_id : land?.owner_id;
        ownsLand = resolvedOwnerId
          ? resolvedOwnerId === user?.user_id
          : ownsLand;
        hasOwner = Boolean(resolvedOwnerId);
        const resolvedFenced =
          landData.fenced !== undefined ? landData.fenced : land?.fenced;
        isFencedVisitor = Boolean(resolvedFenced) && !ownsLand;

        if (!resolvedLandId) {
          setMessages([]);
          setRestrictionReason(null);
          setCanChat(true);
          setChatMode(hasOwner && !ownsLand ? 'message' : 'proximity');
          setCurrentSessionId(null);
          return;
        }

        try {
          const messagesResponse = await chatAPI.getLandMessages(resolvedLandId, 50);
          if (cancelled) {
            return;
          }
          const history = messagesResponse.data?.messages || [];
          const sessionId = messagesResponse.data?.session_id || null;
          const formattedMessages = history.map((msg) => ({
            id: msg.message_id,
            sender: msg.sender_username,
            sender_id: msg.sender_id,
            content: msg.content,
            timestamp: new Date(msg.created_at),
            isHistory: true,
            is_leave_message: msg.is_leave_message,
            read_by_owner: msg.read_by_owner,
          }));

          setMessages(formattedMessages);
          setCurrentSessionId(sessionId);
          if (sessionId) {
            await markMessagesAsRead(sessionId);
          }
          setRestrictionReason(null);
          setCanChat(true);
          setChatMode(hasOwner && !ownsLand ? 'message' : 'proximity');
        } catch (historyError) {
          if (cancelled) {
            return;
          }
          if (historyError.response?.status === 403) {
            setMessages([]);
            setChatMode('restricted');
            setCanChat(false);
            setRestrictionReason(
              historyError.response?.data?.detail ||
                'Only invited guests can read or leave messages on this fenced square.'
            );
            return;
          }
          if (historyError.response?.status === 404) {
            setMessages([]);
            if (!isFencedVisitor) {
              setRestrictionReason(null);
              setCanChat(true);
              setChatMode(hasOwner && !ownsLand ? 'message' : 'proximity');
            } else {
              setChatMode('restricted');
              setCanChat(false);
              setRestrictionReason('This fenced land only allows invited guests.');
            }
            return;
          }
          console.error('Failed to load message history:', historyError);
          setMessages([]);
          setCurrentSessionId(null);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        if (error.response?.status === 404) {
          setMessages([]);
          setRestrictionReason(null);
          setCanChat(true);
          setChatMode('proximity');
          setCurrentSessionId(null);
          return;
        }
        console.error('Failed to load land details for chat history:', error);
        setMessages([]);
        setCurrentSessionId(null);
      }
    };

    loadMessageHistory();

    return () => {
      cancelled = true;
    };
  }, [land, user?.user_id, markMessagesAsRead]);

  useEffect(() => {
    if (!land) {
      setCoLocatedUsers([]);
      return;
    }

    let cancelled = false;

    const loadOnlinePresence = async () => {
      try {
        const response = await wsAPI.getOnlineUsers();
        if (cancelled) return;
        const users = response.data?.users || [];
        const occupants = users.filter((onlineUser) => {
          const location = onlineUser.presence?.location;
          if (!location) return false;
          return (
            Math.floor(location.x) === land.x &&
            Math.floor(location.y) === land.y
          );
        });
        setCoLocatedUsers(occupants);

        const names = {};
        occupants.forEach((occ) => {
          if (occ.user_id) {
            names[occ.user_id] =
              occ.username ||
              occ.presence?.display_name ||
              occ.presence?.username ||
              occ.presence?.name ||
              'Visitor';
          }
        });
        if (Object.keys(names).length > 0) {
          rememberMemberNames(names);
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load online users for presence', error);
        }
      }
    };

    loadOnlinePresence();
    const interval = setInterval(loadOnlinePresence, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [land?.x, land?.y, rememberMemberNames]);

  useEffect(() => {
    if (roomMembers.length > 0) {
      resolveMemberNames(roomMembers);
    }
  }, [roomMembers, resolveMemberNames]);

  // WebSocket connection and message handling
  useEffect(() => {
    if (!currentRoom || chatMode === 'restricted' || !canChat) return;

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

      if (msg.is_leave_message && isOwnLand) {
        markMessagesAsRead();
      }
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
        const members = Array.from(new Set(msg.members || []));
        setRoomMembers(members);
        resolveMemberNames(members);
      }
    });

    // Listen for user joined
    const unsubscribeUserJoined = wsService.on('user_joined', (msg) => {
      if (msg.room_id === currentRoom) {
        let added = false;
        setRoomMembers((prev) => {
          if (!prev.includes(msg.user_id)) {
            added = true;
            return [...prev, msg.user_id];
          }
          return prev;
        });
        if (added) {
          resolveMemberNames([msg.user_id]);
        }
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
  }, [currentRoom, user, resolveMemberNames, chatMode, canChat, isOwnLand, markMessagesAsRead]);

  useEffect(() => {
    // Auto-scroll to bottom
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = (e) => {
    e.preventDefault();
    if (!inputValue.trim()) return;
    if (!canChat || chatMode === 'restricted') {
      toast.error('You do not have permission to send messages here.');
      return;
    }

    wsService.sendMessage(currentRoom, inputValue);
    setInputValue('');

    // Stop typing indicator
    wsService.sendTyping(currentRoom, false);
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
  };

  const handleInputChange = (e) => {
    if (chatMode === 'restricted' || !canChat) return;
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

  const handleAccessSearch = useCallback(async () => {
    if (!land?.land_id) return;
    const term = accessSearchTerm.trim();
    if (!term) {
      setAccessSearchResults([]);
      return;
    }
    setAccessLoading(true);
    try {
      const response = await landsAPI.searchChatAccess(land.land_id, term);
      setAccessSearchResults(response.data || []);
    } catch (error) {
      console.error('Failed to search users for chat access', error);
      toast.error('Failed to search users');
    } finally {
      setAccessLoading(false);
    }
  }, [accessSearchTerm, land?.land_id]);

  const handleGrantAccess = useCallback(
    async (username) => {
      if (!land?.land_id) return;
      setAccessSaving(true);
      try {
        await landsAPI.addChatAccess(land.land_id, {
          username,
          can_read: true,
          can_write: true,
          apply_to_all_fenced: applyToAllFenced,
        });
        toast.success(`Granted chat access to ${username}`);
        await loadAccessEntries();
        setAccessSearchResults((prev) =>
          prev.map((entry) =>
            entry.username === username ? { ...entry, has_access: true } : entry
          )
        );
      } catch (error) {
        console.error('Failed to grant chat access', error);
        toast.error(error.response?.data?.detail || 'Failed to grant access');
      } finally {
        setAccessSaving(false);
      }
    },
    [land?.land_id, loadAccessEntries, applyToAllFenced]
  );

  const handleRevokeAccess = useCallback(
    async (username) => {
      if (!land?.land_id) return;
      setAccessSaving(true);
      try {
        await landsAPI.removeChatAccess(land.land_id, { username });
        toast.success(`Removed chat access for ${username}`);
        await loadAccessEntries();
        setAccessSearchResults((prev) =>
          prev.map((entry) =>
            entry.username === username ? { ...entry, has_access: false } : entry
          )
        );
      } catch (error) {
        console.error('Failed to remove chat access', error);
        toast.error(error.response?.data?.detail || 'Failed to remove access');
      } finally {
        setAccessSaving(false);
      }
    },
    [land?.land_id, loadAccessEntries]
  );

  const getChatTitle = () => {
    if (chatMode === 'restricted') {
      return 'FENCED';
    }
    if (chatMode === 'message') {
      return `Leave Message for ${landOwner || 'Owner'}`;
    }
    if (land) {
      return `Land Chat (${land.x}, ${land.y})`;
    }
    return 'Global Chat';
  };
  const getChatSubtitle = () => {
    if (chatMode === 'restricted') {
      return restrictionReason || `Only ${landOwner || 'the owner'} can receive messages here`;
    }
    if (chatMode === 'message') {
      return `Your message will be saved for the owner`;
    }
    if (land) {
      return `Real-time chat with visitors on this land`;
    }
    return `Chat with nearby players`;
  };

  const chatHeaderTitle = presenceTitle || getChatTitle();
  const chatHeaderSubtitle =
    presenceTitle && presenceSubtitle
      ? presenceSubtitle
      : getChatSubtitle();

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
          <h3 className="text-white font-semibold text-sm md:text-base">{chatHeaderTitle}</h3>
          <div className="flex items-center gap-2">
            <p className="text-[10px] md:text-xs text-gray-400">{chatHeaderSubtitle}</p>
            {roomMembers.length > 0 && chatMode === 'proximity' && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] bg-green-600/30 text-green-300 border border-green-600/50">
                {roomMembers.length} here
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
        {isOwnLand && land?.land_id && land?.fenced && (
          <div className="bg-gray-900/40 border border-gray-700 rounded-lg p-3 mb-2">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10px] uppercase text-gray-500 tracking-wide">Chat Access</p>
                <p className="text-sm text-white">
                  {accessRestricted
                    ? `${accessEntries.length} invited ${accessEntries.length === 1 ? 'guest' : 'guests'}`
                    : 'Open to everyone'}
                </p>
              </div>
              <button
                onClick={() => setShowAccessPanel((prev) => !prev)}
                className="text-xs px-2 py-1 rounded border border-gray-600 text-gray-200 hover:bg-gray-700 transition-colors"
              >
                {showAccessPanel ? 'Hide' : 'Manage'}
              </button>
            </div>
            {showAccessPanel && (
              <div className="mt-3 space-y-3">
                <div className="flex space-x-2">
                  <input
                    type="text"
                    value={accessSearchTerm}
                    onChange={(e) => setAccessSearchTerm(e.target.value)}
                    placeholder="Search username"
                    className="flex-1 px-2 py-1.5 text-sm rounded border border-gray-600 bg-gray-900 text-gray-100 focus:outline-none focus:border-blue-500"
                  />
                  <button
                    type="button"
                    onClick={handleAccessSearch}
                    className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-700 text-white text-sm disabled:opacity-50"
                    disabled={accessLoading}
                  >
                    {accessLoading ? 'Searching...' : 'Search'}
                  </button>
                </div>
                <label className="flex items-center space-x-2 text-xs text-gray-300">
                  <input
                    type="checkbox"
                    className="rounded border-gray-600 bg-gray-900 text-blue-500 focus:ring-blue-500"
                    checked={applyToAllFenced}
                    onChange={(e) => setApplyToAllFenced(e.target.checked)}
                  />
                  <span>Apply to all of my fenced squares</span>
                </label>
                {accessSearchResults.length > 0 && (
                  <div className="bg-gray-900/60 border border-gray-700 rounded-lg max-h-32 overflow-y-auto">
                    {accessSearchResults.map((result) => (
                      <div
                        key={result.user_id}
                        className="flex items-center justify-between px-2 py-1 text-sm text-gray-200 border-b border-gray-800 last:border-b-0"
                      >
                        <span>{result.username}</span>
                        <button
                          type="button"
                          disabled={result.has_access || accessSaving}
                          onClick={() => handleGrantAccess(result.username)}
                          className={`px-2 py-0.5 rounded text-xs ${
                            result.has_access
                              ? 'bg-green-700/40 text-green-200 cursor-default'
                              : 'bg-green-600 hover:bg-green-700 text-white'
                          }`}
                        >
                          {result.has_access ? 'Added' : 'Grant access'}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div>
                  <p className="text-xs text-gray-400 mb-1">People who can view & leave messages:</p>
                  {accessEntries.length === 0 ? (
                    <p className="text-xs text-gray-500">No invited guests yet — chat is open to everyone.</p>
                  ) : (
                    <ul className="space-y-1">
                      {accessEntries.map((entry) => (
                        <li
                          key={entry.access_id}
                          className="flex items-center justify-between text-sm text-gray-100 bg-gray-900/60 border border-gray-800 rounded px-2 py-1"
                        >
                          <span>{entry.username}</span>
                          <button
                            type="button"
                            className="text-xs text-red-300 hover:text-red-200"
                            disabled={accessSaving}
                            onClick={() => handleRevokeAccess(entry.username)}
                          >
                            Remove
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
        {chatMode === 'restricted' ? (
          <div className="text-center text-red-400 mt-8">
            <div className="w-16 h-16 mx-auto mb-4 bg-red-900/50 rounded-full flex items-center justify-center">
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <p className="text-lg font-semibold mb-2">Chat access restricted</p>
            <p className="text-sm text-gray-300">{restrictionReason || `Only ${landOwner || 'the owner'} can receive messages here`}</p>
            <p className="text-xs text-gray-500 mt-3">The owner has limited who can read or leave messages on this square.</p>
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
            <p className="text-red-400 text-sm font-semibold">Chat Disabled</p>
            <p className="text-xs text-gray-400 mt-1">Chat Disabled</p>
          </div>
        )}
      </form>
    </div>
  );
}

export default ChatBox;
