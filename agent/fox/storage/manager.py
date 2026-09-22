# Fox Storage Manager - Deterministic storage accounting and quota enforcement

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .exceptions import StorageQuotaError


# Directories that count toward Fox Space storage usage.
# These are directories inside Fox Space that can contain user data.
# system/, config/ are read-only and shouldn't have new user data.
# trash/ counts because deleted files moved to trash still consume space.
# apps/ counts as it can have user-installed apps.
COUNTED_DIRS = frozenset({
    "workspace",
    "storage",
    "apps",
    "trash",
})

# Directories that should NOT count toward storage (read-only or system-managed)
UNCOUNTED_DIRS = frozenset({
    "system",
    "config",
})


@dataclass(frozen=True)
class StorageInfo:
    """Storage usage information for Fox Space."""
    used_bytes: int
    limit_bytes: Optional[int]
    available_bytes: Optional[int]
    usage_percent: Optional[float]

    def to_dict(self) -> dict:
        return {
            "used_bytes": self.used_bytes,
            "used_mb": round(self.used_bytes / (1024 * 1024), 2),
            "limit_bytes": self.limit_bytes,
            "limit_mb": round(self.limit_bytes / (1024 * 1024), 2) if self.limit_bytes else None,
            "available_bytes": self.available_bytes,
            "available_mb": round(self.available_bytes / (1024 * 1024), 2) if self.available_bytes else None,
            "usage_percent": round(self.usage_percent, 2) if self.usage_percent else None,
        }


class FoxStorageManager:
    """
    Deterministic storage accounting and quota enforcement for Fox Space.

    This class provides deterministic storage accounting for Fox Space.
    It calculates the total size of files in counted directories and
    enforces a configurable quota before write operations.

    The storage accounting is deterministic and does not use background
    daemons, databases, or external services.
    """

    def __init__(
        self,
        root: str | Path,
        quota_bytes: Optional[int] = None,
    ):
        """
        Initialize the storage manager.

        Args:
            root: The Fox Space root directory.
            quota_bytes: Optional maximum storage limit in bytes. None means no limit.
        """
        self._root = Path(root).expanduser().resolve()
        self._quota_bytes = quota_bytes

        # Validate root exists
        if not self._root.exists():
            raise ValueError(f"Fox Space root does not exist: {self._root}")
        if not self._root.is_dir():
            raise ValueError(f"Fox Space root is not a directory: {self._root}")

    @property
    def root(self) -> Path:
        return self._root

    @property
    def quota_bytes(self) -> Optional[int]:
        return self._quota_bytes

    @quota_bytes.setter
    def quota_bytes(self, value: Optional[int]) -> None:
        if value is not None and value < 0:
            raise ValueError("Quota cannot be negative")
        self._quota_bytes = value

    def _is_counted_path(self, path: Path) -> bool:
        """Check if a path is inside a counted directory."""
        try:
            relative = path.relative_to(self._root)
        except ValueError:
            return False

        if not relative.parts:
            return False

        first_part = relative.parts[0]
        return first_part in COUNTED_DIRS

    def _walk_counted_files(self):
        """Walk all counted files in Fox Space, yielding (path, size)."""
        for counted_dir in COUNTED_DIRS:
            dir_path = self._root / counted_dir
            if not dir_path.exists():
                continue

            for file_path in dir_path.rglob("*"):
                if not file_path.is_file():
                    continue

                # Skip if the file is a symlink that escapes
                try:
                    resolved = file_path.resolve(strict=True)
                except (OSError, FileNotFoundError):
                    # Broken symlink - skip
                    continue

                # Ensure resolved path is still within Fox Space
                try:
                    resolved.relative_to(self._root)
                except ValueError:
                    # Symlink escapes Fox Space - skip
                    continue

                yield file_path, file_path.stat().st_size

    def calculate_usage(self) -> int:
        """
        Calculate total storage usage in bytes.

        Returns:
            Total bytes used in counted directories.
        """
        total = 0
        for _, size in self._walk_counted_files():
            total += size
        return total

    def get_storage_info(self) -> StorageInfo:
        """
        Get current storage usage information.

        Returns:
            StorageInfo with current usage, limit, and available space.
        """
        used = self.calculate_usage()
        limit = self._quota_bytes

        if limit is not None:
            available = max(0, limit - used)
            usage_percent = (used / limit) * 100 if limit > 0 else 0.0
        else:
            available = None
            usage_percent = None

        return StorageInfo(
            used_bytes=used,
            limit_bytes=limit,
            available_bytes=available,
            usage_percent=usage_percent,
        )

    def check_quota(self, additional_bytes: int = 0) -> None:
        """
        Check if adding additional_bytes would exceed the quota.

        Args:
            additional_bytes: Additional bytes that would be added.

        Raises:
            StorageQuotaError: If the operation would exceed the quota.
        """
        if self._quota_bytes is None:
            return  # No limit set

        current = self.calculate_usage()
        projected = current + additional_bytes

        if projected > self._quota_bytes:
            raise StorageQuotaError(
                f"Storage quota exceeded: "
                f"current={self._format_bytes(current)}, "
                f"requested={self._format_bytes(additional_bytes)}, "
                f"limit={self._format_bytes(self._quota_bytes)}, "
                f"would exceed by {self._format_bytes(projected - self._quota_bytes)}"
            )

    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes into human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f}PB"

    def check_quota_for_write(self, source_path: Path, dest_path: Path, operation: str) -> None:
        """
        Check quota for a write operation.

        This method calculates the storage delta for different operations
        and checks if the operation would exceed the quota.

        Args:
            source_path: Source file path (for copy/move).
            dest_path: Destination file path.
            operation: Type of operation ('create', 'write', 'copy', 'move', 'restore', 'delete').

        Raises:
            StorageQuotaError: If the operation would exceed the quota.
        """
        if self._quota_bytes is None:
            return

        current = self.calculate_usage()

        if operation == "create":
            # Creating a new empty file - minimal impact
            additional = 0

        elif operation == "write":
            # Writing to a file - calculate delta
            dest_size = dest_path.stat().st_size if dest_path.exists() else 0
            # We don't know the new size, so check if current usage is near limit
            # This is a conservative check - actual delta depends on write content
            additional = 0

        elif operation == "copy":
            # Copying a file adds the source file size
            if source_path.exists() and source_path.is_file():
                additional = source_path.stat().st_size
            else:
                additional = 0

        elif operation == "move":
            # Moving within Fox Space doesn't change total usage
            # (unless moving from uncounted to counted dir, which policy prevents)
            source_is_counted = self._is_counted_path(source_path)
            dest_is_counted = self._is_counted_path(dest_path)

            if source_is_counted and dest_is_counted:
                # Moving within counted dirs - no net change
                additional = 0
            elif not source_is_counted and dest_is_counted:
                # Moving from uncounted to counted (should be blocked by policy)
                if source_path.exists() and source_path.is_file():
                    additional = source_path.stat().st_size
                else:
                    additional = 0
            else:
                # Moving from counted to uncounted (should be blocked)
                additional = 0

        elif operation == "restore":
            # Restore from trash - file already counted in trash, so no net change
            additional = 0

        elif operation == "delete":
            # Delete (move to trash) - file still counted in trash
            additional = 0

        elif operation == "empty_trash":
            # Empty trash reduces usage - no quota check needed
            additional = 0

        else:
            additional = 0

        # Check if the operation would exceed quota
        projected = current + additional
        if self._quota_bytes is not None and projected > self._quota_bytes:
            raise StorageQuotaError(
                f"Storage quota exceeded: "
                f"current={self._format_bytes(current)}, "
                f"requested={self._format_bytes(additional)}, "
                f"limit={self._format_bytes(self._quota_bytes)}"
            )

    def get_usage_breakdown(self) -> dict[str, int]:
        """
        Get storage usage broken down by directory.

        Returns:
            Dictionary mapping directory name to bytes used.
        """
        breakdown = {}
        for counted_dir in COUNTED_DIRS:
            dir_path = self._root / counted_dir
            if not dir_path.exists():
                breakdown[counted_dir] = 0
                continue

            total = 0
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    try:
                        resolved = file_path.resolve(strict=True)
                        resolved.relative_to(self._root)
                        total += file_path.stat().st_size
                    except (OSError, FileNotFoundError, ValueError):
                        continue
            breakdown[counted_dir] = total

        return breakdown