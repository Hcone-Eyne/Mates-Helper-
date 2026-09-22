# Storage Exceptions

class StorageError(Exception):
    """Base exception for storage errors."""
    pass


class StorageQuotaError(StorageError):
    """
    Raised when a storage operation would exceed the configured quota.

    Attributes:
        current_bytes: Current storage usage in bytes.
        requested_bytes: Additional bytes requested.
        limit_bytes: Configured quota limit in bytes.
    """

    def __init__(
        self,
        message: str,
        current_bytes: int = 0,
        requested_bytes: int = 0,
        limit_bytes: int = 0,
    ):
        super().__init__(message)
        self.current_bytes = current_bytes
        self.requested_bytes = requested_bytes
        self.limit_bytes = limit_bytes