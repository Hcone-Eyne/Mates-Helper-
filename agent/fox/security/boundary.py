# Fox Security Boundary
# Deterministic application-level security layer for Fox filesystem operations.
# LLMs are NEVER the security authority.

from pathlib import Path
from typing import Literal


class FoxSecurityError(PermissionError):
    """Raised when an operation violates Fox security policy."""
    pass


class InvalidActionError(FoxSecurityError):
    """Raised when an unknown or disallowed action is requested."""
    pass


class PathEscapeError(FoxSecurityError):
    """Raised when a path attempts to escape the Fox root."""
    pass


class SymlinkEscapeError(FoxSecurityError):
    """Raised when a symlink resolves outside the Fox root."""
    pass


class FoxSecurityBoundary:
    """
    Deterministic security boundary for Fox filesystem operations.

    The Fox root is established once at construction and cannot be changed.
    All paths are validated against this root using proper path semantics.

    LLMs (Julie, Annie, Selina, Gwen, Ollama) are NEVER the security authority.
    This boundary is the single choke point for all filesystem access.
    """

    # Supported actions - centralized action policy
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

    # Action aliases for natural-language compatibility
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

    # Trash directory name
    TRASH_DIR = ".fox_trash"

    def __init__(self, root: str | Path, create: bool = True):
        """
        Establish the Fox security root.

        The root is resolved once and cannot be changed after construction.
        This prevents operations from bypassing the boundary by providing
        a different target directory per operation.

        Args:
            root: The root directory path
            create: If True, create the root directory if it doesn't exist (default: True)
        """
        self._root = Path(root).expanduser().resolve()

        if not self._root.exists():
            if create:
                self._root.mkdir(parents=True, exist_ok=True)
            else:
                raise ValueError(f"Fox root does not exist: {self._root}")
        elif not self._root.is_dir():
            raise ValueError(f"Fox root is not a directory: {self._root}")

        # Create trash directory
        self._trash_dir = self._root / self.TRASH_DIR
        self._trash_dir.mkdir(parents=True, exist_ok=True)

        # Mark root as immutable
        self._sealed = True

    @property
    def root(self) -> Path:
        """Return the immutable Fox security root."""
        return self._root

    @property
    def trash_dir(self) -> Path:
        """Return the trash directory path."""
        return self._trash_dir

    def __setattr__(self, name: str, value) -> None:
        """Prevent modification of sealed attributes after initialization."""
        if getattr(self, "_sealed", False) and name in ("_root", "_trash_dir", "_sealed"):
            raise FoxSecurityError("FoxSecurityBoundary root is immutable after construction")
        super().__setattr__(name, value)

    # ------------------------------------------------------------------
    # Path validation
    # ------------------------------------------------------------------

    def validate_path(self, path: str | Path, must_exist: bool = False) -> Path:
        """
        Validate and resolve a path against the Fox security root.

        Args:
            path: The path to validate (relative to Fox root or absolute)
            must_exist: If True, the path must exist on disk

        Returns:
            The resolved absolute path inside the Fox root

        Raises:
            PathEscapeError: If the path resolves outside the Fox root
            SymlinkEscapeError: If a symlink resolves outside the Fox root
            FileNotFoundError: If must_exist=True and path doesn't exist
        """
        candidate = Path(path).expanduser()

        # If path is relative, treat it as relative to Fox root
        if not candidate.is_absolute():
            candidate = (self._root / candidate).resolve()

        # Handle nonexistent paths - resolve parent directories
        try:
            resolved = candidate.resolve()
        except FileNotFoundError:
            # For nonexistent paths, resolve as much as possible
            # Find the nearest existing ancestor
            parts = candidate.parts
            for i in range(len(parts), 0, -1):
                test_path = Path(*parts[:i])
                if test_path.exists():
                    resolved = test_path.resolve()
                    # Append remaining parts
                    for part in parts[i:]:
                        resolved = resolved / part
                    break
            else:
                # No existing ancestor, use the root as base
                resolved = candidate

        # Check if path escapes the Fox root
        if not self._is_inside_root(resolved):
            raise PathEscapeError(
                f"Path escapes Fox security root: {path} -> {resolved}"
            )

        # Check for symlink escape
        if candidate.exists() and candidate.is_symlink():
            try:
                real_resolved = candidate.resolve(strict=True)
                if not self._is_inside_root(real_resolved):
                    raise SymlinkEscapeError(
                        f"Symlink escapes Fox security root: {path} -> {real_resolved}"
                    )
            except (OSError, FileNotFoundError):
                # Broken symlink or other issue - treat as escape attempt
                raise SymlinkEscapeError(f"Symlink resolution failed: {path}")

        if must_exist and not resolved.exists():
            raise FileNotFoundError(f"Path does not exist: {resolved}")

        return resolved

    def _is_inside_root(self, path: Path) -> bool:
        """Check if a resolved path is inside the Fox root using path semantics."""
        try:
            # Path is inside root if root is the path itself or an ancestor
            return path == self._root or self._root in path.parents
        except (ValueError, OSError):
            return False

    def validate_source_path(self, path: str | Path) -> Path:
        """Validate a source path (must exist)."""
        return self.validate_path(path, must_exist=True)

    def validate_destination_path(self, path: str | Path, allow_new: bool = True) -> Path:
        """
        Validate a destination path.

        Args:
            path: The destination path
            allow_new: If True, allow paths that don't exist yet (for creation)

        Returns:
            The resolved destination path
        """
        return self.validate_path(path, must_exist=not allow_new)

    def validate_new_name(self, name: str) -> str:
        """
        Validate a new filename (not a path).

        Rejects:
        - Path traversal attempts (.., /, \\)
        - Absolute paths
        - Empty names
        """
        name = name.strip()
        if not name:
            raise FoxSecurityError("Filename cannot be empty")

        # Reject path components
        if any(part in name for part in ("..", "/", "\\")):
            raise FoxSecurityError(f"Invalid filename (contains path components): {name}")

        # Reject absolute paths
        if Path(name).is_absolute():
            raise FoxSecurityError(f"Filename cannot be an absolute path: {name}")

        return name

    # ------------------------------------------------------------------
    # Action validation
    # ------------------------------------------------------------------

    def resolve_action(self, action: str) -> str:
        """
        Resolve an action name, handling aliases.

        Returns the canonical action name.
        Raises InvalidActionError if action is unknown.
        """
        action = action.strip().lower().replace(" ", "_")

        # Check aliases first
        if action in self.ACTION_ALIASES:
            return self.ACTION_ALIASES[action]

        # Check if it's a known action
        if action in self.SUPPORTED_ACTIONS:
            return action

        raise InvalidActionError(
            f"Unknown action: '{action}'. Supported: {sorted(self.SUPPORTED_ACTIONS)}"
        )

    def validate_action(self, action: str) -> str:
        """Validate and return canonical action name."""
        return self.resolve_action(action)

    def is_trash_path(self, path: Path) -> bool:
        """Check if a path is inside the trash directory."""
        try:
            resolved = path.resolve()
            return self._trash_dir in resolved.parents or resolved == self._trash_dir
        except (ValueError, OSError):
            return False

    def get_relative_path(self, path: Path) -> Path:
        """Get path relative to Fox root."""
        resolved = path.resolve()
        if not self._is_inside_root(resolved):
            raise PathEscapeError(f"Path not inside Fox root: {path}")
        return resolved.relative_to(self._root)

    def ensure_parent_dirs(self, path: Path) -> Path:
        """Ensure parent directories exist for a path inside Fox root."""
        validated = self.validate_path(path, must_exist=False)
        validated.parent.mkdir(parents=True, exist_ok=True)
        return validated