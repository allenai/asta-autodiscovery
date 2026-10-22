"""Shared dataset upload limits for run input endpoints."""

# Max size of files that can be uploaded
UPLOAD_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 * 1024  # 50GB default
UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_BYTES = (
    100 * 1024 * 1024 * 1024
)  # 100GB for users with higher upload limit permission
UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_STR = "100GB"
