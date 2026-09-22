# Fox Security Boundary
#
# Deterministic application-level security layer for Fox filesystem operations.
# LLMs are NEVER the security authority.
#
# IMPORTANT:
# This is an application-level boundary, not an OS sandbox.
# A compromised process with unrestricted host permissions could still bypass it.
# Strong process isolation belongs to a later OS/container/VM phase.

from pathlib import Path
import os

from .policy import FoxDirectoryPolicy, FoxPolicyError, FoxSecurityError
from agent.fox.storage import FoxStorageManager


class InvalidActionError(FoxSecurityError):
    """Raised when an unknown or disallowed action is requested."""


class PathEscapeError(FoxSecurityError):
    """Raised when a path attempts to escape the Fox root."""


class SymlinkEscapeError(FoxSecurityError):
    """Raised when a symlink resolves outside the Fox root."""


class PrivilegedActionError(FoxSecurityError):
    """Raised when a privileged action lacks explicit security authorization."""


class FoxSecurityBoundary:
    """
    Deterministic security boundary for Fox filesystem operations.

    LLMs may REQUEST actions.
    They do NOT authorize actions.

    The boundary owns:
    - root containment
    - symlink validation
    - action allowlisting
    - privileged-action authorization
    - trash containment
    - directory-area authorization (via FoxDirectoryPolicy)
    """

    SUPPORTED_ACTIONS = frozenset({
        "list_directory",
        "organise_folder",
        "move_file",
        "copy_file",
        "rename_file",
        "create_folder",
        "delete_file",
        "search_files",
        "restore_file",
        "empty_trash",
    })

    ACTION_ALIASES = {
        "move": "move_file",
        "copy": "copy_file",
        "rename": "rename_file",
        "mkdir": "create_folder",
        "delete": "delete_file",
        "organise": "organise_folder",
        "organize": "organise_folder",
        "sort": "organise_folder",
        "categorize": "organise_folder",
        "list": "list_directory",
        "show": "list_directory",
        "display": "list_directory",
        "find": "search_files",
        "search": "search_files",
        "locate": "search_files",
        "look": "search_files",
    }

    PRIVILEGED_ACTIONS = frozenset({
        "empty_trash",
    })

    TRASH_DIR = ".fox_trash"

    # Directory policy constants (mirrored from FoxDirectoryPolicy for convenience)
    READ_ONLY_DIRS = frozenset({
        "system",
        "apps",
        "config",
    })

    WRITEABLE_DIRS = frozenset({
        "workspace",
        "storage",
    })
    WRITABLE_DIRS = WRITEABLE_DIRS

    RESERVED_DIRS = frozenset({
        ".fox_trash",
        "trash",
    })

    def __init__(
        self,
        root: str | Path,
        create: bool = True,
        storage_quota_bytes: int | None = None,
    ):
        root_path = Path(root).expanduser()

        # Normalize the root for lexical comparisons (don't resolve symlinks).
        # Store both normalized and resolved forms.
        root_path = Path(os.path.normpath(str(root_path)))

        if not root_path.exists():
            if not create:
                raise ValueError(
                    f"Fox root does not exist: {root_path}"
                )
            root_path.mkdir(parents=True, exist_ok=True)

        if not root_path.is_dir():
            raise ValueError(
                f"Fox root is not a directory: {root_path}"
            )

        # Use resolved root for trash to handle macOS /tmp -> /private/tmp symlink
        trash_path = Path(root_path).resolve() / self.TRASH_DIR

        if trash_path.exists() and not trash_path.is_dir():
            raise ValueError(
                f"Fox trash path is not a directory: {trash_path}"
            )

        trash_path.mkdir(parents=True, exist_ok=True)

        # Store normalized root for lexical comparisons
        # Also store resolved root for symlink resolution
        object.__setattr__(self, "_root", root_path)
        object.__setattr__(self, "_root_resolved", Path(root_path).resolve())
        object.__setattr__(self, "_trash_dir", trash_path)
        object.__setattr__(self, "_trash_dir_resolved", trash_path)
        object.__setattr__(self, "_policy", FoxDirectoryPolicy(root_path))
        object.__setattr__(self, "_storage_manager", FoxStorageManager(root_path, storage_quota_bytes))
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value) -> None:
        if getattr(self, "_sealed", False):
            if name in {"_root", "_trash_dir", "_policy", "_sealed"}:
                raise FoxSecurityError(
                    "FoxSecurityBoundary root is immutable after construction"
                )

        super().__setattr__(name, value)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def trash_dir(self) -> Path:
        return self._trash_dir

    @property
    def root_resolved(self) -> Path:
        return self._root_resolved

    @property
    def policy(self) -> FoxDirectoryPolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Path validation
    # ------------------------------------------------------------------

    def validate_path(
        self,
        path: str | Path,
        must_exist: bool = False,
    ) -> Path:
        """
        Validate a path against the Fox root.

        Relative paths are interpreted relative to Fox root.

        Existing path components are resolved to detect symlink escapes.

        Nonexistent final components are allowed when must_exist=False,
        provided their existing parent chain remains inside the root.
        """

        if path is None:
            raise PathEscapeError("Path cannot be None")

        candidate = Path(path).expanduser()

        if not candidate.is_absolute():
            candidate = self._root / candidate

        # Validate component chain first to catch symlink escapes before
        # checking root containment of the resolved path.
        self._validate_component_chain(candidate)

        # Resolve existing components while allowing a nonexistent leaf.
        try:
            resolved = candidate.resolve(strict=False)
        except OSError as exc:
            raise PathEscapeError(
                f"Unable to resolve path safely: {path}"
            ) from exc

        if not self._is_inside_root_resolved(resolved):
            raise PathEscapeError(
                f"Path escapes Fox security root: {path} -> {resolved}"
            )

        if must_exist and not candidate.exists():
            raise FileNotFoundError(
                f"Path does not exist: {candidate}"
            )

        return resolved

    def _validate_component_chain(self, candidate: Path) -> None:
        """
        Validate the complete existing component chain.

        This catches:
        - direct symlink escapes
        - nested symlink escapes
        - symlinked parent directories
        - broken symlinks
        """

        # First, check if the path (without resolving symlinks) is inside root.
        # This allows symlinks inside the root to be validated individually.
        try:
            relative = candidate.relative_to(self._root)
        except ValueError:
            # If the unresolved path fails, try with resolved paths
            # (handles macOS /tmp -> /private/tmp symlink).
            try:
                candidate_resolved = candidate.resolve(strict=False)
            except OSError:
                candidate_resolved = candidate
            try:
                relative = candidate_resolved.relative_to(self._root)
            except ValueError:
                # If still fails, try against resolved root (handles macOS /tmp -> /private/tmp)
                try:
                    relative = candidate_resolved.relative_to(self._root_resolved)
                except ValueError as exc:
                    raise PathEscapeError(
                        f"Path is outside Fox root: {candidate}"
                    ) from exc

        # If candidate is the root itself, there are no components to validate.
        if not relative.parts:
            return

        current = self._root

        for component in relative.parts:
            current = current / component

            if current.is_symlink():
                try:
                    resolved = current.resolve(strict=True)
                except (OSError, FileNotFoundError) as exc:
                    raise SymlinkEscapeError(
                        f"Unable to safely resolve symlink: {current}"
                    ) from exc

                if not self._is_inside_root_resolved(resolved):
                    raise SymlinkEscapeError(
                        f"Symlink escapes Fox root: "
                        f"{current} -> {resolved}"
                    )

    def _is_inside_root(self, path: Path) -> bool:
        try:
            path.relative_to(self._root)
            return True
        except ValueError:
            return False

    def _is_inside_root_resolved(self, path: Path) -> bool:
        try:
            path.relative_to(self._root_resolved)
            return True
        except ValueError:
            return False

    def _is_lexically_within_root(self, path: Path) -> bool:
        """Check whether an absolute path is inside the root without following symlinks."""
        # Use normpath for both root and candidate to handle symlinks lexically
        root = Path(os.path.normpath(str(self._root)))
        normalized = Path(os.path.normpath(str(path)))

        try:
            normalized.relative_to(root)
            return True
        except ValueError:
            return False

    def validate_source_path(self, path: str | Path) -> Path:
        return self.validate_path(path, must_exist=True)

    def validate_destination_path(
        self,
        path: str | Path,
        allow_new: bool = True,
    ) -> Path:
        return self.validate_path(
            path,
            must_exist=not allow_new,
        )

    def validate_new_name(self, name: str) -> str:
        if not isinstance(name, str):
            raise FoxSecurityError("Filename must be a string")

        name = name.strip()

        if not name:
            raise FoxSecurityError("Filename cannot be empty")

        if name in {".", ".."}:
            raise FoxSecurityError(
                "Invalid filename"
            )

        if "/" in name or "\\" in name:
            raise FoxSecurityError(
                f"Invalid filename: {name}"
            )

        if Path(name).is_absolute():
            raise FoxSecurityError(
                f"Filename cannot be an absolute path: {name}"
            )

        return name

    # ------------------------------------------------------------------
    # Action validation
    # ------------------------------------------------------------------

    def resolve_action(self, action: str) -> str:
        if not isinstance(action, str):
            raise InvalidActionError(
                "Action must be a string"
            )

        normalized = (
            action.strip()
            .lower()
            .replace(" ", "_")
        )

        if normalized in self.ACTION_ALIASES:
            return self.ACTION_ALIASES[normalized]

        if normalized in self.SUPPORTED_ACTIONS:
            return normalized

        raise InvalidActionError(
            f"Unknown action: '{normalized}'. "
            f"Supported: {sorted(self.SUPPORTED_ACTIONS)}"
        )

    def validate_action(self, action: str) -> str:
        return self.resolve_action(action)

    # ------------------------------------------------------------------
    # Privileged actions
    # ------------------------------------------------------------------

    def authorize_privileged_action(
        self,
        action: str,
        *,
        authorization_token: object | None = None,
    ) -> str:
        """
        Authorize a privileged action.

        IMPORTANT:
        A boolean such as confirm=True is deliberately NOT accepted.

        The token must be created by trusted application code, not by
        LLM-generated action arguments.
        """

        canonical = self.validate_action(action)

        if canonical not in self.PRIVILEGED_ACTIONS:
            return canonical

        if authorization_token is not self:
            raise PrivilegedActionError(
                f"Privileged action requires trusted authorization: "
                f"{canonical}"
            )

        return canonical

    # ------------------------------------------------------------------
    # Policy-based authorization methods
    # ------------------------------------------------------------------

    def validate_read(self, path: str | Path) -> Path:
        """Validate that a path can be read according to policy."""
        return self._policy.validate_read(path)

    def validate_write(self, path: str | Path) -> Path:
        """Validate that a path can be written according to policy."""
        return self._policy.validate_write(path)

    def validate_create(self, path: str | Path) -> Path:
        """Validate that a path can be created."""
        return self._policy.validate_create(path)

    def validate_delete(self, path: str | Path) -> Path:
        """Validate that a path can be deleted."""
        return self._policy.validate_delete(path)

    def validate_move_source(self, path: str | Path) -> Path:
        """Validate that a source path can be moved."""
        return self._policy.validate_move_source(path)

    def validate_copy_source(self, path: str | Path) -> Path:
        """Validate that a source can be copied (read-only areas allowed)."""
        return self._policy.validate_copy_source(path)

    def validate_move_destination(self, path: str | Path) -> Path:
        """Validate that a destination can receive a moved file."""
        return self._policy.validate_move_destination(path)

    def validate_copy_destination(self, path: str | Path) -> Path:
        """Validate that a destination can receive a copied file."""
        return self._policy.validate_write(path)

    def validate_organise_target(self, path: str | Path) -> Path:
        """Validate that a target can be organised."""
        return self._policy.validate_organise_target(path)

    def validate_restore_destination(self, path: str | Path, allow_new: bool = True) -> Path:
        """Validate that a restore destination is allowed."""
        return self._policy.validate_restore_destination(path)

    def validate_rename_source(self, path: str | Path) -> Path:
        """Validate that a file can be renamed (must be writable)."""
        return self._policy.validate_write(path)

    def validate_rename_destination(self, path: str | Path) -> Path:
        """Validate rename destination (must be writable, filename only)."""
        return self._policy.validate_write(path)

    def get_area(self, path: str | Path) -> str:
        """Get the Fox Space area for a path (system, apps, config, workspace, storage, trash, root)."""
        return self._policy.area(path)

    def area(self, path: str | Path) -> str:
        """Alias for get_area for backward compatibility."""
        return self._policy.area(path)

    # ------------------------------------------------------------------
    # Storage quota management
    # ------------------------------------------------------------------

    @property
    def storage_manager(self) -> "FoxStorageManager":
        """Get the storage manager instance."""
        return self._storage_manager

    @property
    def storage_quota_bytes(self) -> int | None:
        """Get the configured storage quota in bytes."""
        return self._storage_manager.quota_bytes

    @storage_quota_bytes.setter
    def storage_quota_bytes(self, value: int | None) -> None:
        self._storage_manager.quota_bytes = value

    def get_storage_info(self) -> "StorageInfo":
        """Get current storage usage information."""
        return self._storage_manager.get_storage_info()

    def get_storage_breakdown(self) -> dict[str, int]:
        """Get storage usage broken down by directory."""
        return self._storage_manager.get_usage_breakdown()

    def check_storage_quota(self, additional_bytes: int = 0) -> None:
        """
        Check if adding additional_bytes would exceed the storage quota.

        Raises:
            StorageQuotaError: If the operation would exceed the quota.
        """
        self._storage_manager.check_quota(additional_bytes)

    def check_storage_quota_for_write(
        self,
        source_path: Path,
        dest_path: Path,
        operation: str,
    ) -> None:
        """
        Check quota for a specific write operation.

        Args:
            source_path: Source file path (for copy/move).
            dest_path: Destination file path.
            operation: Type of operation ('create', 'write', 'copy', 'move', 'restore', 'delete', 'empty_trash').

        Raises:
            StorageQuotaError: If the operation would exceed the quota.
        """
        self._storage_manager.check_quota_for_write(source_path, dest_path, operation)

    # ------------------------------------------------------------------
    # Trash policy
    # ------------------------------------------------------------------

    def is_trash_path(self, path: Path) -> bool:
        try:
            resolved = Path(path).resolve(strict=False)
        except OSError:
            return False

        try:
            resolved.relative_to(self._trash_dir_resolved)
            return True
        except ValueError:
            return False

    def validate_trash_path(
        self,
        path: str | Path,
        *,
        must_exist: bool = False,
    ) -> Path:
        """
        Validate that a path is inside Fox trash.
        """

        resolved = self.validate_path(
            path,
            must_exist=must_exist,
        )

        if not self.is_trash_path(resolved):
            raise FoxSecurityError(
                f"Path is not inside Fox trash: {path}"
            )

        return resolved

    def validate_trash_write(self, path: str | Path) -> Path:
        """
        Validate a path inside trash for write operations (move to trash, delete from trash).
        This bypasses the normal RESERVED_DIRS check for trash operations.
        """

        resolved = self.validate_path(
            path,
            must_exist=False,
        )

        if not self.is_trash_path(resolved):
            raise FoxSecurityError(
                f"Path is not inside Fox trash: {path}"
            )

        return resolved

    # ------------------------------------------------------------------
    # Utility operations
    # ------------------------------------------------------------------

    def get_relative_path(self, path: Path) -> Path:
        resolved = self.validate_path(path)

        try:
            return resolved.relative_to(self._root_resolved)
        except ValueError as exc:
            raise PathEscapeError(
                f"Path not inside Fox root: {path}"
            ) from exc

    def ensure_parent_dirs(self, path: Path) -> Path:
        """
        Validate a path and create its parent directories.

        This remains application-level protection. It does not eliminate
        filesystem TOCTOU races against another hostile process.
        """

        validated = self.validate_destination_path(
            path,
            allow_new=True,
        )

        parent = validated.parent

        # Validate the parent independently before creation.
        self.validate_destination_path(
            parent,
            allow_new=True,
        )

        parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Revalidate after creation.
        return self.validate_destination_path(
            validated,
            allow_new=True,
        )