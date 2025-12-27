"""
File upload service
Handles file uploads for avatars, documents, etc.
"""

import os
import uuid
from pathlib import Path
from typing import Optional
import logging
from fastapi import UploadFile

logger = logging.getLogger(__name__)

# File upload configuration
UPLOAD_DIR = Path("backend/uploads")
AVATAR_DIR = UPLOAD_DIR / "avatars"
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_AVATAR_TYPES = {"image/png", "image/jpeg", "image/jpg"}


class FileUploadService:
    """Service for handling file uploads."""

    @staticmethod
    def ensure_upload_dirs():
        """Create upload directories if they don't exist."""
        AVATAR_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Upload directories ready: {UPLOAD_DIR}")

    @staticmethod
    async def upload_avatar(file: UploadFile, user_id: str) -> str:
        """
        Upload and store user avatar.

        Args:
            file: UploadFile from FastAPI
            user_id: UUID of the user

        Returns:
            str: Relative path to the saved avatar

        Raises:
            ValueError: If file is invalid
        """
        FileUploadService.ensure_upload_dirs()

        # Validate file type
        if file.content_type not in ALLOWED_AVATAR_TYPES:
            raise ValueError(
                f"Invalid file type. Allowed: {', '.join(ALLOWED_AVATAR_TYPES)}"
            )

        # Validate file size
        contents = await file.read()
        if len(contents) > MAX_AVATAR_SIZE:
            raise ValueError(f"File too large. Max size: {MAX_AVATAR_SIZE} bytes")

        # Generate unique filename
        file_extension = Path(file.filename).suffix.lower()
        unique_filename = f"{user_id}_{uuid.uuid4()}{file_extension}"
        file_path = AVATAR_DIR / unique_filename

        # Save file
        try:
            with open(file_path, "wb") as f:
                f.write(contents)
            logger.info(f"Avatar uploaded: {unique_filename}")

            # Return relative path for storage in database
            return f"/uploads/avatars/{unique_filename}"
        except Exception as e:
            logger.error(f"Failed to save avatar: {str(e)}")
            raise

    @staticmethod
    def delete_avatar(avatar_url: Optional[str]) -> bool:
        """
        Delete avatar file if it exists.

        Args:
            avatar_url: URL or path of avatar to delete

        Returns:
            bool: True if deleted, False otherwise
        """
        if not avatar_url:
            return False

        try:
            # Extract filename from URL
            if avatar_url.startswith("/uploads/avatars/"):
                filename = avatar_url.replace("/uploads/avatars/", "")
                file_path = AVATAR_DIR / filename

                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Avatar deleted: {filename}")
                    return True
        except Exception as e:
            logger.error(f"Failed to delete avatar: {str(e)}")

        return False


# Singleton instance
file_upload_service = FileUploadService()
