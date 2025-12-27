/**
 * UserProfileCard Component
 * Displays user profile with avatar, name, bio, ban status
 * Supports edit mode with image upload and bio editing
 */

import { useState } from "react";
import toast from "react-hot-toast";
import { usersAPI } from "../services/api";

function UserProfileCard({
  user,
  isOwnProfile = false,
  isAdmin = false,
  onUpdate = null,
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editingBio, setEditingBio] = useState(user?.bio || "");
  const [avatarFile, setAvatarFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(user?.avatar_url || null);
  const [isLoading, setIsLoading] = useState(false);

  const handleAvatarChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Validate file type
    const validTypes = ["image/png", "image/jpeg", "image/jpg"];
    if (!validTypes.includes(file.type)) {
      toast.error("Only PNG and JPEG images are allowed");
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Image must be less than 5MB");
      return;
    }

    setAvatarFile(file);
    // Show preview
    const reader = new FileReader();
    reader.onloadend = () => {
      setPreviewUrl(reader.result);
    };
    reader.readAsDataURL(file);
  };

  const handleSaveProfile = async () => {
    try {
      setIsLoading(true);

      const updates = {
        bio: editingBio,
      };

      // Upload avatar if changed
      if (avatarFile) {
        const formData = new FormData();
        formData.append("file", avatarFile);
        const uploadRes = await usersAPI.uploadAvatar(user.user_id, formData);
        updates.avatar_url = uploadRes.data.avatar_url;
      }

      // Update user profile
      const updateRes = await usersAPI.updateProfile(user.user_id, updates);

      toast.success("Profile updated successfully");
      setIsEditing(false);
      setAvatarFile(null);

      if (onUpdate) {
        onUpdate(updateRes.data.user);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update profile");
      console.error("Profile update error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const canEdit = isOwnProfile || isAdmin;

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 mb-6">
      <div className="flex items-start gap-6">
        {/* Avatar Section */}
        <div className="flex flex-col items-center">
          <div className="relative">
            <img
              src={previewUrl || "/default-avatar.png"}
              alt={user?.username}
              className="w-24 h-24 rounded-full bg-gray-700 object-cover border-2 border-blue-600"
            />
            {isEditing && canEdit && (
              <label className="absolute bottom-0 right-0 bg-blue-600 hover:bg-blue-700 text-white rounded-full p-2 cursor-pointer transition-colors">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/jpg"
                  onChange={handleAvatarChange}
                  className="hidden"
                />
              </label>
            )}
          </div>
          {!isEditing && canEdit && (
            <button
              onClick={() => setIsEditing(true)}
              className="mt-3 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
            >
              Edit Profile
            </button>
          )}
        </div>

        {/* Profile Info Section */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between mb-3">
            <div>
              <h2 className="text-2xl font-bold">{user?.username}</h2>
              <p className="text-gray-400 text-sm">{user?.email}</p>
            </div>
            {user?.is_banned && (
              <div className="flex items-center gap-2 px-3 py-1 bg-red-900 border border-red-600 rounded-lg">
                <svg
                  className="w-4 h-4 text-red-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4v2m0 4v2M7.08 6.47A9 9 0 1120.92 17.53M7.08 6.47L5.6 5"
                  />
                </svg>
                <span className="text-red-300 text-sm font-semibold">
                  Banned
                </span>
              </div>
            )}
          </div>

          {/* Bio Section */}
          <div className="mb-4">
            <p className="text-gray-400 text-sm font-semibold mb-2">Bio</p>
            {isEditing && canEdit ? (
              <textarea
                value={editingBio}
                onChange={(e) => setEditingBio(e.target.value.slice(0, 500))}
                placeholder="Tell others about yourself..."
                maxLength={500}
                className="w-full bg-gray-700 border border-gray-600 text-white rounded-lg p-3 focus:outline-none focus:border-blue-500 resize-none"
                rows={3}
              />
            ) : (
              <p className="text-gray-300 text-sm">
                {user?.bio || (
                  <span className="text-gray-500 italic">No bio added</span>
                )}
              </p>
            )}
            {isEditing && canEdit && (
              <p className="text-gray-500 text-xs mt-1">
                {editingBio.length}/500 characters
              </p>
            )}
          </div>

          {/* Ban Reason (if banned) */}
          {user?.is_banned && user?.ban_reason && (
            <div className="mb-4 p-3 bg-red-900/20 border border-red-700 rounded-lg">
              <p className="text-red-400 text-sm font-semibold mb-1">
                Ban Reason:
              </p>
              <p className="text-red-300 text-sm">{user.ban_reason}</p>
            </div>
          )}

          {/* Action Buttons */}
          {isEditing && canEdit ? (
            <div className="flex gap-2">
              <button
                onClick={handleSaveProfile}
                disabled={isLoading}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isLoading ? (
                  <>
                    <svg
                      className="w-4 h-4 animate-spin"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                      />
                    </svg>
                    Saving...
                  </>
                ) : (
                  <>
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    Save
                  </>
                )}
              </button>
              <button
                onClick={() => {
                  setIsEditing(false);
                  setEditingBio(user?.bio || "");
                  setPreviewUrl(user?.avatar_url || null);
                  setAvatarFile(null);
                }}
                disabled={isLoading}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default UserProfileCard;
