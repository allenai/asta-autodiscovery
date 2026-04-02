"""Service for managing user.json files in GCS.

This module provides a UserProfile data class and functions for creating,
reading, and updating user profiles stored in GCS. Each user can have a
user.json file that stores custom settings like credit allocation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from google.cloud import storage
from google.api_core import retry as google_retry

from .config import JobConfig

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    """Data class representing user profile stored in GCS.

    Attributes:
        granted_credits: Custom credit allocation for user (None = use default)
        created_at: ISO timestamp when profile was created
        updated_at: ISO timestamp when profile was last updated
    """

    granted_credits: int | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "granted_credits": self.granted_credits,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserProfile:
        """Create from dictionary (e.g., from JSON)."""
        return cls(
            granted_credits=data.get("granted_credits"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    @classmethod
    def create_new(cls, granted_credits: int | None = None) -> UserProfile:
        """Create a new UserProfile with current timestamp.

        Args:
            granted_credits: Custom credit allocation (None = use default)

        Returns:
            New UserProfile instance
        """
        now = datetime.now(UTC).isoformat()
        return cls(
            granted_credits=granted_credits,
            created_at=now,
            updated_at=now,
        )


def get_user_profile_path(userid: str) -> str:
    """Get the GCS blob path for user.json.

    Args:
        userid: User identifier

    Returns:
        Blob path for user.json
    """
    return f"users/{userid}/user.json"


def create_user_profile(
    userid: str,
    granted_credits: int | None = None,
    config: JobConfig | None = None,
) -> UserProfile:
    """Create initial user.json file.

    Args:
        userid: User identifier
        granted_credits: Custom credit allocation (None = use default)
        config: Job configuration (uses default if None)

    Returns:
        The created UserProfile object

    Raises:
        ValueError: If granted_credits is negative
    """
    if granted_credits is not None and granted_credits < 0:
        raise ValueError(f"granted_credits must be non-negative, got {granted_credits}")

    config = config or JobConfig.from_env()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    user_profile = UserProfile.create_new(granted_credits=granted_credits)

    blob_path = get_user_profile_path(userid)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(user_profile.to_dict(), indent=2))

    return user_profile


def get_user_profile(
    userid: str,
    config: JobConfig | None = None,
) -> UserProfile | None:
    """Get user profile from GCS.

    Args:
        userid: User identifier
        config: Job configuration (uses default if None)

    Returns:
        UserProfile object, or None if not found or on error
    """
    config = config or JobConfig.from_env()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    blob_path = get_user_profile_path(userid)
    blob = bucket.blob(blob_path)

    try:
        content = blob.download_as_text(timeout=2, retry=None)
        data = json.loads(content)
        return UserProfile.from_dict(data)
    except Exception as e:
        logger.debug(f"Could not load user profile for {userid}: {e}")
        return None


def update_user_profile(
    userid: str,
    updates: dict[str, Any],
    config: JobConfig | None = None,
) -> UserProfile:
    """Update user profile in GCS.

    Automatically sets updated_at timestamp.

    Args:
        userid: User identifier
        updates: Dictionary of fields to update
        config: Job configuration (uses default if None)

    Returns:
        Updated UserProfile object

    Raises:
        ValueError: If granted_credits is negative
    """
    # Validate granted_credits if being updated
    if "granted_credits" in updates:
        credits = updates["granted_credits"]
        if credits is not None and credits < 0:
            raise ValueError(f"granted_credits must be non-negative, got {credits}")

    config = config or JobConfig.from_env()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    # Get existing profile
    user_profile = get_user_profile(userid, config)
    if not user_profile:
        user_profile = UserProfile.create_new()

    user_profile_dict = user_profile.to_dict()

    # Update fields and timestamp
    user_profile_dict.update(updates)
    user_profile_dict["updated_at"] = datetime.now(UTC).isoformat()

    # Save back to GCS
    blob_path = get_user_profile_path(userid)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(user_profile_dict, indent=2))

    return UserProfile.from_dict(user_profile_dict)


def get_user_granted_credits(
    userid: str,
    config: JobConfig | None = None,
) -> int | None:
    """Get custom granted credits for a user.

    Args:
        userid: User identifier
        config: Job configuration (uses default if None)

    Returns:
        Custom granted credits, or None if not set (use default)
    """
    profile = get_user_profile(userid, config)
    if profile is None:
        return None
    return profile.granted_credits
