/**
 * Admin Communication Page
 * Manage announcements and broadcast messages
 */

import { useState, useEffect } from "react";
import { adminAPI } from "../services/api";
import useAuthStore from "../stores/authStore";
import toast from "react-hot-toast";

function AdminCommunicationPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState("announcements");
  const [announcements, setAnnouncements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({
    title: "",
    message: "",
    type: "info",
    target_audience: "all",
    display_location: "banner",
    start_date: "",
    end_date: "",
  });
  const [broadcastData, setBroadcastData] = useState({
    title: "System Announcement",
    message: "",
    target: "all",
  });
  const [pushToggles, setPushToggles] = useState({
    push_enabled: true,
    push_daily_limit: 50,
    quiet_hours_enabled: false,
    quiet_hours_start: "22:00",
    quiet_hours_end: "07:00",
  });
  const [emailSettings, setEmailSettings] = useState({
    email_enabled: true,
    email_rate_limit_per_minute: 60,
    smtp_host: "",
    smtp_port: 587,
    smtp_user: "",
    smtp_password: "",
    smtp_tls_enabled: true,
  });
  const [savingComm, setSavingComm] = useState(false);

  useEffect(() => {
    if (user?.role !== "admin") {
      toast.error("Admin access required");
      return;
    }
    if (activeTab === "announcements") {
      loadAnnouncements();
    } else if (activeTab === "notifications") {
      loadNotifications();
    } else if (activeTab === "email") {
      loadEmailSettings();
    }
  }, [user, activeTab]);

  const loadAnnouncements = async () => {
    setLoading(true);
    try {
      const res = await adminAPI.getAnnouncements({ active_only: false });
      setAnnouncements(res.data.data);
    } catch (error) {
      toast.error("Failed to load announcements");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const loadNotifications = async () => {
    setLoading(true);
    try {
      const [featuresRes, limitsRes] = await Promise.all([
        adminAPI.getFeatureToggles(),
        adminAPI.getSystemLimits(),
      ]);
      setPushToggles((prev) => ({
        ...prev,
        push_enabled: !!featuresRes.data?.push_enabled,
        quiet_hours_enabled: !!featuresRes.data?.quiet_hours_enabled,
        quiet_hours_start:
          featuresRes.data?.quiet_hours_start || prev.quiet_hours_start,
        quiet_hours_end:
          featuresRes.data?.quiet_hours_end || prev.quiet_hours_end,
        push_daily_limit:
          limitsRes.data?.push_daily_limit ?? prev.push_daily_limit,
      }));
    } catch (error) {
      toast.error("Failed to load notification settings");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const loadEmailSettings = async () => {
    setLoading(true);
    try {
      const [featuresRes, limitsRes] = await Promise.all([
        adminAPI.getFeatureToggles(),
        adminAPI.getSystemLimits(),
      ]);
      setEmailSettings((prev) => ({
        ...prev,
        email_enabled: !!featuresRes.data?.email_enabled,
        email_rate_limit_per_minute:
          limitsRes.data?.email_rate_limit_per_minute ??
          prev.email_rate_limit_per_minute,
        smtp_host: featuresRes.data?.smtp_host || "",
        smtp_port: featuresRes.data?.smtp_port ?? 587,
        smtp_user: featuresRes.data?.smtp_user || "",
        smtp_tls_enabled: !!featuresRes.data?.smtp_tls_enabled,
      }));
    } catch (error) {
      toast.error("Failed to load email settings");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitAnnouncement = async (e) => {
    e.preventDefault();
    try {
      if (editingId) {
        await adminAPI.updateAnnouncement(editingId, formData);
        toast.success("Announcement updated successfully");
      } else {
        await adminAPI.createAnnouncement(formData);
        toast.success("Announcement created successfully");
      }
      setShowForm(false);
      setEditingId(null);
      setFormData({
        title: "",
        message: "",
        type: "info",
        target_audience: "all",
        display_location: "banner",
        start_date: "",
        end_date: "",
      });
      loadAnnouncements();
    } catch (error) {
      toast.error("Failed to save announcement");
      console.error(error);
    }
  };

  const handleEditAnnouncement = (announcement) => {
    setEditingId(announcement.announcement_id);
    setFormData({
      title: announcement.title,
      message: announcement.message,
      type: announcement.type,
      target_audience: announcement.target_audience,
      display_location: announcement.display_location,
      start_date: announcement.start_date
        ? announcement.start_date.split("T")[0]
        : "",
      end_date: announcement.end_date
        ? announcement.end_date.split("T")[0]
        : "",
    });
    setShowForm(true);
  };

  const handleDeleteAnnouncement = async (id) => {
    if (!window.confirm("Are you sure you want to delete this announcement?"))
      return;

    try {
      await adminAPI.deleteAnnouncement(id);
      toast.success("Announcement deleted successfully");
      loadAnnouncements();
    } catch (error) {
      toast.error("Failed to delete announcement");
      console.error(error);
    }
  };

  const handleSendBroadcast = async (e) => {
    e.preventDefault();
    if (!broadcastData.message.trim()) {
      toast.error("Message cannot be empty");
      return;
    }

    if (!window.confirm(`Send broadcast to ${broadcastData.target}?`)) return;

    try {
      await adminAPI.sendBroadcast(broadcastData);
      toast.success("Broadcast sent successfully");
      setBroadcastData({
        title: "System Announcement",
        message: "",
        target: "all",
      });
    } catch (error) {
      toast.error("Failed to send broadcast");
      console.error(error);
    }
  };

  const handleSaveNotifications = async () => {
    if (
      pushToggles.push_daily_limit < 1 ||
      pushToggles.push_daily_limit > 10000
    ) {
      toast.error("Daily limit out of bounds (1-10000)");
      return;
    }
    setSavingComm(true);
    try {
      await adminAPI.updateFeatureToggles({
        push_enabled: pushToggles.push_enabled,
        quiet_hours_enabled: pushToggles.quiet_hours_enabled,
        quiet_hours_start: pushToggles.quiet_hours_start,
        quiet_hours_end: pushToggles.quiet_hours_end,
      });
      await adminAPI.updateSystemLimits({
        push_daily_limit: pushToggles.push_daily_limit,
      });
      toast.success("Notification settings saved");
    } catch (error) {
      toast.error("Failed to save notification settings");
      console.error(error);
    } finally {
      setSavingComm(false);
    }
  };

  const handleSaveEmail = async () => {
    if (emailSettings.email_rate_limit_per_minute < 1) {
      toast.error("Email rate limit must be >= 1");
      return;
    }
    setSavingComm(true);
    try {
      await adminAPI.updateFeatureToggles({
        email_enabled: emailSettings.email_enabled,
        smtp_host: emailSettings.smtp_host,
        smtp_port: emailSettings.smtp_port,
        smtp_user: emailSettings.smtp_user,
        smtp_tls_enabled: emailSettings.smtp_tls_enabled,
      });
      await adminAPI.updateSystemLimits({
        email_rate_limit_per_minute: emailSettings.email_rate_limit_per_minute,
      });
      toast.success("Email settings saved");
    } catch (error) {
      toast.error("Failed to save email settings");
      console.error(error);
    } finally {
      setSavingComm(false);
    }
  };

  if (user?.role !== "admin") {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-400 mb-4">
            Access Denied
          </h1>
          <p className="text-gray-400">
            You need admin privileges to access this page.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-2">Communication</h1>
          <p className="text-gray-400">
            Manage announcements and broadcast messages
          </p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        {/* Tabs */}
        <div className="flex space-x-4 mb-6 border-b border-gray-700">
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "announcements"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => setActiveTab("announcements")}
          >
            Announcements
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "broadcast"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => setActiveTab("broadcast")}
          >
            Broadcast Message
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "notifications"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => setActiveTab("notifications")}
          >
            Notifications
          </button>
          <button
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === "email"
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => setActiveTab("email")}
          >
            Email Settings
          </button>
        </div>

        {/* Announcements Tab */}
        {activeTab === "announcements" && (
          <div>
            <div className="mb-6">
              <button
                onClick={() => {
                  setShowForm(!showForm);
                  setEditingId(null);
                  setFormData({
                    title: "",
                    message: "",
                    type: "info",
                    target_audience: "all",
                    display_location: "banner",
                    start_date: "",
                    end_date: "",
                  });
                }}
                className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded font-semibold"
              >
                {showForm ? "Cancel" : "+ New Announcement"}
              </button>
            </div>

            {/* Announcement Form */}
            {showForm && (
              <form
                onSubmit={handleSubmitAnnouncement}
                className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6"
              >
                <h3 className="text-xl font-bold mb-4">
                  {editingId ? "Edit" : "Create"} Announcement
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Title
                    </label>
                    <input
                      type="text"
                      value={formData.title}
                      onChange={(e) =>
                        setFormData({ ...formData, title: e.target.value })
                      }
                      required
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Message
                    </label>
                    <textarea
                      value={formData.message}
                      onChange={(e) =>
                        setFormData({ ...formData, message: e.target.value })
                      }
                      required
                      rows={4}
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Type
                    </label>
                    <select
                      value={formData.type}
                      onChange={(e) =>
                        setFormData({ ...formData, type: e.target.value })
                      }
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    >
                      <option value="info">Info</option>
                      <option value="warning">Warning</option>
                      <option value="urgent">Urgent</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Target Audience
                    </label>
                    <select
                      value={formData.target_audience}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          target_audience: e.target.value,
                        })
                      }
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    >
                      <option value="all">All Users</option>
                      <option value="admins">Admins Only</option>
                      <option value="users">Regular Users</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Display Location
                    </label>
                    <select
                      value={formData.display_location}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          display_location: e.target.value,
                        })
                      }
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    >
                      <option value="banner">Banner</option>
                      <option value="popup">Popup</option>
                      <option value="both">Both</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Start Date (Optional)
                    </label>
                    <input
                      type="date"
                      value={formData.start_date}
                      onChange={(e) =>
                        setFormData({ ...formData, start_date: e.target.value })
                      }
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      End Date (Optional)
                    </label>
                    <input
                      type="date"
                      value={formData.end_date}
                      onChange={(e) =>
                        setFormData({ ...formData, end_date: e.target.value })
                      }
                      className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded font-semibold"
                >
                  {editingId ? "Update" : "Create"} Announcement
                </button>
              </form>
            )}

            {/* Announcements List */}
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
              </div>
            ) : (
              <div className="space-y-4">
                {announcements.map((announcement) => (
                  <div
                    key={announcement.announcement_id}
                    className="bg-gray-800 rounded-lg p-6 border border-gray-700"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          <h3 className="text-xl font-bold">
                            {announcement.title}
                          </h3>
                          <span
                            className={`px-2 py-1 rounded text-xs font-semibold ${
                              announcement.type === "urgent"
                                ? "bg-red-900 text-red-200"
                                : announcement.type === "warning"
                                ? "bg-yellow-900 text-yellow-200"
                                : "bg-blue-900 text-blue-200"
                            }`}
                          >
                            {announcement.type}
                          </span>
                        </div>
                        <p className="text-gray-300 mb-3">
                          {announcement.message}
                        </p>
                        <div className="flex items-center space-x-4 text-sm text-gray-400">
                          <span>Target: {announcement.target_audience}</span>
                          <span>Display: {announcement.display_location}</span>
                          {announcement.start_date && (
                            <span>
                              Start:{" "}
                              {new Date(
                                announcement.start_date
                              ).toLocaleDateString()}
                            </span>
                          )}
                          {announcement.end_date && (
                            <span>
                              End:{" "}
                              {new Date(
                                announcement.end_date
                              ).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex space-x-2 ml-4">
                        <button
                          onClick={() => handleEditAnnouncement(announcement)}
                          className="text-blue-400 hover:text-blue-300 font-semibold"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() =>
                            handleDeleteAnnouncement(
                              announcement.announcement_id
                            )
                          }
                          className="text-red-400 hover:text-red-300 font-semibold"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
                {announcements.length === 0 && (
                  <div className="text-center py-12 text-gray-400 bg-gray-800 rounded-lg">
                    No announcements yet. Create one to get started!
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Broadcast Tab */}
        {activeTab === "broadcast" && (
          <form
            onSubmit={handleSendBroadcast}
            className="bg-gray-800 rounded-lg p-6 border border-gray-700"
          >
            <h3 className="text-xl font-bold mb-4">Send Broadcast Message</h3>

            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Title
                </label>
                <input
                  type="text"
                  value={broadcastData.title}
                  onChange={(e) =>
                    setBroadcastData({
                      ...broadcastData,
                      title: e.target.value,
                    })
                  }
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Message
                </label>
                <textarea
                  value={broadcastData.message}
                  onChange={(e) =>
                    setBroadcastData({
                      ...broadcastData,
                      message: e.target.value,
                    })
                  }
                  required
                  rows={6}
                  placeholder="Enter your broadcast message..."
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Target
                </label>
                <select
                  value={broadcastData.target}
                  onChange={(e) =>
                    setBroadcastData({
                      ...broadcastData,
                      target: e.target.value,
                    })
                  }
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                >
                  <option value="all">All Users</option>
                  <option value="online">Online Users Only</option>
                  <option value="admins">Admins Only</option>
                  <option value="users">Regular Users</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              className="bg-green-600 hover:bg-green-700 px-8 py-3 rounded font-semibold"
            >
              Send Broadcast
            </button>

            <p className="text-sm text-yellow-400 mt-4">
              ⚠️ Note: WebSocket implementation required for real-time delivery.
              Currently logs to audit trail.
            </p>
          </form>
        )}

        {/* Notifications Tab */}
        {activeTab === "notifications" && (
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-xl font-bold mb-4">Push Notifications</h3>
            <div className="space-y-6">
              <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
                <div>
                  <h4 className="font-semibold mb-1">
                    Enable Push Notifications
                  </h4>
                  <p className="text-sm text-gray-400">
                    Toggle push notifications for users
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={pushToggles.push_enabled}
                    onChange={(e) =>
                      setPushToggles({
                        ...pushToggles,
                        push_enabled: e.target.checked,
                      })
                    }
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 rounded-full peer peer-checked:bg-blue-600"></div>
                </label>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Daily Push Limit
                  </label>
                  <input
                    type="number"
                    value={pushToggles.push_daily_limit}
                    onChange={(e) =>
                      setPushToggles({
                        ...pushToggles,
                        push_daily_limit: parseInt(e.target.value || "0"),
                      })
                    }
                    className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-300">
                    Quiet Hours
                  </label>
                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={pushToggles.quiet_hours_enabled}
                        onChange={(e) =>
                          setPushToggles({
                            ...pushToggles,
                            quiet_hours_enabled: e.target.checked,
                          })
                        }
                      />
                      <span>Enabled</span>
                    </label>
                    <input
                      type="time"
                      value={pushToggles.quiet_hours_start}
                      onChange={(e) =>
                        setPushToggles({
                          ...pushToggles,
                          quiet_hours_start: e.target.value,
                        })
                      }
                      className="bg-gray-700 text-white px-3 py-2 rounded border border-gray-600"
                    />
                    <span>to</span>
                    <input
                      type="time"
                      value={pushToggles.quiet_hours_end}
                      onChange={(e) =>
                        setPushToggles({
                          ...pushToggles,
                          quiet_hours_end: e.target.value,
                        })
                      }
                      className="bg-gray-700 text-white px-3 py-2 rounded border border-gray-600"
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-6 border-t border-gray-700 mt-6">
                <button
                  onClick={handleSaveNotifications}
                  disabled={savingComm}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-8 py-3 rounded font-semibold transition-colors"
                >
                  {savingComm ? "Saving..." : "Save Notifications"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Email Settings Tab */}
        {activeTab === "email" && (
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-xl font-bold mb-4">Email Configuration</h3>
            <div className="space-y-6">
              <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
                <div>
                  <h4 className="font-semibold mb-1">Enable Email System</h4>
                  <p className="text-sm text-gray-400">
                    Toggle transactional emails
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={emailSettings.email_enabled}
                    onChange={(e) =>
                      setEmailSettings({
                        ...emailSettings,
                        email_enabled: e.target.checked,
                      })
                    }
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 rounded-full peer peer-checked:bg-blue-600"></div>
                </label>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Email Rate Limit (per minute)
                  </label>
                  <input
                    type="number"
                    value={emailSettings.email_rate_limit_per_minute}
                    onChange={(e) =>
                      setEmailSettings({
                        ...emailSettings,
                        email_rate_limit_per_minute: parseInt(
                          e.target.value || "0"
                        ),
                      })
                    }
                    className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    SMTP Host
                  </label>
                  <input
                    type="text"
                    value={emailSettings.smtp_host}
                    onChange={(e) =>
                      setEmailSettings({
                        ...emailSettings,
                        smtp_host: e.target.value,
                      })
                    }
                    className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    SMTP Port
                  </label>
                  <input
                    type="number"
                    value={emailSettings.smtp_port}
                    onChange={(e) =>
                      setEmailSettings({
                        ...emailSettings,
                        smtp_port: parseInt(e.target.value || "0"),
                      })
                    }
                    className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    SMTP Username
                  </label>
                  <input
                    type="text"
                    value={emailSettings.smtp_user}
                    onChange={(e) =>
                      setEmailSettings({
                        ...emailSettings,
                        smtp_user: e.target.value,
                      })
                    }
                    className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    SMTP Password
                  </label>
                  <input
                    type="password"
                    value={emailSettings.smtp_password}
                    onChange={(e) =>
                      setEmailSettings({
                        ...emailSettings,
                        smtp_password: e.target.value,
                      })
                    }
                    className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    TLS Enabled
                  </label>
                  <input
                    type="checkbox"
                    checked={emailSettings.smtp_tls_enabled}
                    onChange={(e) =>
                      setEmailSettings({
                        ...emailSettings,
                        smtp_tls_enabled: e.target.checked,
                      })
                    }
                  />
                </div>
              </div>

              <div className="flex justify-between items-center pt-6 border-t border-gray-700 mt-6">
                <p className="text-sm text-yellow-400">
                  Note: SMTP credentials may be managed via environment in
                  production.
                </p>
                <button
                  onClick={handleSaveEmail}
                  disabled={savingComm}
                  className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 px-8 py-3 rounded font-semibold transition-colors"
                >
                  {savingComm ? "Saving..." : "Save Email Settings"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default AdminCommunicationPage;
