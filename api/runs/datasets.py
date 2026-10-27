"""Shared dataset filename validation and upload limits for run input endpoints."""

from io import RawIOBase
from typing import BinaryIO

# Max size of files that can be uploaded
UPLOAD_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 * 1024  # 50GB default
UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_BYTES = (
    100 * 1024 * 1024 * 1024
)  # 100GB for users with higher upload limit permission
UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_STR = "100GB"


def is_valid_dataset_filename(filename: str) -> bool:
    """Keep names verbatim while rejecting path components and control characters."""
    return (
        isinstance(filename, str)
        and bool(filename)
        and filename not in (".", "..")
        and "/" not in filename
        and "\\" not in filename
        and not any(ord(char) < 32 or ord(char) == 127 for char in filename)
    )


class LimitedDatasetReader(RawIOBase):
    """Bound decoded bytes read by a store, regardless of advertised source sizes."""

    def __init__(self, source: BinaryIO, max_size: int):
        super().__init__()
        self._source = source
        self._max_size = max_size
        self._bytes_read = 0
        # Backends may wrap the read error in StorageError; retain its cause here.
        self.limit_exceeded = False

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._bytes_read

    def readinto(self, buffer) -> int:
        if self.limit_exceeded:
            raise ValueError("File too large.")
        data = self._source.read(min(len(buffer), self._max_size - self._bytes_read + 1))
        self._bytes_read += len(data)
        if self._bytes_read > self._max_size:
            self.limit_exceeded = True
            raise ValueError("File too large.")
        buffer[: len(data)] = data
        return len(data)
