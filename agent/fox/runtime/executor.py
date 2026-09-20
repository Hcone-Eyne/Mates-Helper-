# Fox FileActionExecutor
# Adapts Selina's ActionExecutor protocol to work with FoxSecurityBoundary.
# All filesystem operations go through the deterministic security boundary.

import shutil
from pathlib import Path
from typing import Any, Union

from File_Manager import preferences
from agent.fox.security import FoxSecurityBoundary, FoxSecurityError, InvalidActionError


# Reuse the canonical category list from the existing organizer.
CATEGORIES = [
    "Documents", "Notes", "Code", "Images",
    "Audio", "Video", "Archives", "Other"
]


class FileActionExecutor:
    """
    Satisfies Selina's ActionExecutor protocol.

    All paths are validated through FoxSecurityBoundary.
    The executor receives a pre-configured boundary, not an arbitrary target directory.
    """

    def __init__(self, boundary: Union[FoxSecurityBoundary, Path, str]):
        """
        Initialize with a FoxSecurityBoundary or a path (for backward compatibility).

        If a path is provided, a FoxSecurityBoundary is created internally.
        The boundary's root is the security authority.
        The target directory is the boundary's root.
        """
        if isinstance(boundary, FoxSecurityBoundary):
            self._boundary = boundary
        else:
            # Backward compatibility: create boundary from path
            self._boundary = FoxSecurityBoundary(boundary)

        self._target = self._boundary.root

    # ------------------------------------------------------------------
    # Backward compatibility: _assert_inside
    # ------------------------------------------------------------------

    def _assert_inside(self, path: Path) -> Path:
        """
        Backward compatibility: validate path is inside target.

        Delegates to boundary's validate_source_path.
        """
        try:
            return self._boundary.validate_source_path(path)
        except FoxSecurityError as e:
            # Convert to expected error message for backward compatibility
            raise PermissionError(f"Path escapes the target directory: {path}")

    # ------------------------------------------------------------------
    # ActionExecutor protocol
    # ------------------------------------------------------------------

    def execute(self, action: str, arguments: dict[str, Any]) -> Any:
        """Execute an action with arguments, validated through security boundary."""
        # Resolve and validate action through boundary
        try:
            canonical_action = self._boundary.validate_action(action)
        except InvalidActionError as e:
            raise RuntimeError(f"Unknown action '{action}'. Supported: {', '.join(sorted(self._boundary.SUPPORTED_ACTIONS))}")

        # Dispatch to internal methods
        if canonical_action == "organise_folder":
            return self._organise_folder(arguments)

        if canonical_action == "list_directory":
            return self._list_directory(arguments)

        if canonical_action == "move_file":
            return self._move_file(arguments)

        if canonical_action == "copy_file":
            return self._copy_file(arguments)

        if canonical_action == "rename_file":
            return self._rename_file(arguments)

        if canonical_action == "create_folder":
            return self._create_folder(arguments)

        if canonical_action == "delete_file":
            return self._delete_file(arguments)

        if canonical_action == "search_files":
            return self._search_files(arguments)

        if canonical_action == "restore_file":
            return self._restore_file(arguments)

        if canonical_action == "empty_trash":
            return self._empty_trash(arguments)

        raise RuntimeError(
            f"[FileActionExecutor]: Unknown action '{action}'. "
            f"Supported: {', '.join(sorted(self._boundary.SUPPORTED_ACTIONS))}"
        )

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _validate_source(self, path: str | Path) -> Path:
        """Validate a source path (must exist)."""
        return self._boundary.validate_source_path(path)

    def _validate_destination(self, path: str | Path, allow_new: bool = True) -> Path:
        """Validate a destination path."""
        return self._boundary.validate_destination_path(path, allow_new=allow_new)

    def _validate_new_name(self, name: str) -> str:
        """Validate a new filename (not a path)."""
        return self._boundary.validate_new_name(name)

    def _ensure_parent_dirs(self, path: Path) -> Path:
        """Ensure parent directories exist."""
        return self._boundary.ensure_parent_dirs(path)

    def _get_relative(self, path: Path) -> Path:
        """Get path relative to Fox root."""
        return self._boundary.get_relative_path(path)

    def _is_trash(self, path: Path) -> bool:
        """Check if path is in trash."""
        return self._boundary.is_trash_path(path)

    def _resolve_collision(self, dest_path: Path) -> Path:
        """Resolve filename collision by appending _1, _2, etc."""
        counter = 1
        stem = dest_path.stem
        suffix = dest_path.suffix
        parent = dest_path.parent

        while dest_path.exists():
            dest_path = parent / f"{stem}_{counter}{suffix}"
            counter += 1

        return dest_path

    # ------------------------------------------------------------------
    # organise_folder
    # ------------------------------------------------------------------

    def _organise_folder(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Scan the target directory, create category subdirectories,
        and move each file into its category folder.

        Returns a summary dict with counts per category.
        """
        moved: dict[str, list[str]] = {cat: [] for cat in CATEGORIES}

        for entry in sorted(self._target.iterdir()):
            # Skip directories — only move regular files.
            if not entry.is_file():
                continue

            # Skip trash directory
            if self._is_trash(entry):
                continue

            # Verify the source file is inside the target directory.
            self._validate_source(entry)

            ext = entry.suffix.lower()
            category = preferences.category_for(ext)

            dest_dir = self._target / category
            dest_dir.mkdir(parents=True, exist_ok=True)

            dest_path = dest_dir / entry.name

            # Handle duplicate filenames inside the category folder.
            dest_path = self._resolve_collision(dest_path)

            # Verify the destination is inside the target directory.
            self._validate_destination(dest_path)

            shutil.move(str(entry), str(dest_path))
            moved[category].append(entry.name)

        # Build a human-readable summary for Selina's result.
        summary_parts: list[str] = []
        for cat in CATEGORIES:
            files = moved[cat]
            if files:
                summary_parts.append(f"{cat}: {', '.join(files)}")

        return {
            "target": str(self._target),
            "moved": {cat: files for cat, files in moved.items() if files},
            "summary": "; ".join(summary_parts) if summary_parts else "No files to organise.",
        }

    # ------------------------------------------------------------------
    # list_directory
    # ------------------------------------------------------------------

    def _list_directory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """List entries in the target directory.

        Accepts a ``recursive`` boolean argument (default False).
        When False, lists only immediate children.
        When True, lists all descendants recursively.

        Returns a dict with ``entries`` (list of relative path strings),
        ``count`` (int), and ``summary`` (human-readable string).
        Strictly read-only — nothing is modified.
        Hides .fox_trash by default.
        """
        recursive: bool = arguments.get("recursive", False)
        show_trash: bool = arguments.get("show_trash", False)

        entries: list[str] = []

        if recursive:
            for path in sorted(self._target.rglob("*")):
                # Skip trash directory
                if not show_trash and self._is_trash(path):
                    continue

                self._validate_source(path)
                rel = path.relative_to(self._target)
                entries.append(str(rel))
        else:
            for path in sorted(self._target.iterdir()):
                # Skip trash directory
                if not show_trash and self._is_trash(path):
                    continue

                self._validate_source(path)
                rel = path.relative_to(self._target)
                entries.append(str(rel))

        count = len(entries)

        if count == 0:
            summary = "Directory is empty."
        elif recursive:
            summary = f"{count} entries (recursive)."
        else:
            summary = f"{count} entries."

        return {
            "target": str(self._target),
            "recursive": recursive,
            "entries": entries,
            "count": count,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # move_file
    # ------------------------------------------------------------------

    def _move_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Move a file from source to destination.

        Arguments:
            source: Source file path (relative to Fox root or absolute)
            destination: Destination path (relative to Fox root or absolute)
            overwrite: If True, overwrite existing file (default: False, uses collision resolution)

        Returns structured result.
        """
        source = arguments.get("source")
        destination = arguments.get("destination")
        overwrite = arguments.get("overwrite", False)

        if source is None or destination is None:
            raise FoxSecurityError("move_file requires 'source' and 'destination' arguments")

        # Validate source (must exist)
        src_path = self._validate_source(source)

        if not src_path.is_file():
            raise FoxSecurityError(f"Source is not a file: {src_path}")

        # Skip if source is in trash
        if self._is_trash(src_path):
            raise FoxSecurityError("Cannot move files from trash directly; use restore_file")

        # Validate destination
        dest_path = self._validate_destination(destination, allow_new=True)

        # If destination is a directory, move file into it with same name
        if dest_path.exists() and dest_path.is_dir():
            dest_path = dest_path / src_path.name

        # Handle collisions
        if dest_path.exists() and not overwrite:
            dest_path = self._resolve_collision(dest_path)

        # Verify destination is inside root
        self._validate_destination(dest_path)

        # Ensure parent directories exist
        self._ensure_parent_dirs(dest_path)

        # Move the file
        shutil.move(str(src_path), str(dest_path))

        return {
            "action": "move_file",
            "source": str(self._get_relative(src_path)),
            "destination": str(self._get_relative(dest_path)),
            "success": True,
        }

    # ------------------------------------------------------------------
    # copy_file
    # ------------------------------------------------------------------

    def _copy_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Copy a file from source to destination.

        Arguments:
            source: Source file path (relative to Fox root or absolute)
            destination: Destination path (relative to Fox root or absolute)
            overwrite: If True, overwrite existing file (default: False, uses collision resolution)

        Returns structured result.
        """
        source = arguments.get("source")
        destination = arguments.get("destination")
        overwrite = arguments.get("overwrite", False)

        if source is None or destination is None:
            raise FoxSecurityError("copy_file requires 'source' and 'destination' arguments")

        # Validate source (must exist)
        src_path = self._validate_source(source)

        if not src_path.is_file():
            raise FoxSecurityError(f"Source is not a file: {src_path}")

        # Skip if source is in trash
        if self._is_trash(src_path):
            raise FoxSecurityError("Cannot copy files from trash directly; use restore_file")

        # Validate destination
        dest_path = self._validate_destination(destination, allow_new=True)

        # If destination is a directory, copy file into it with same name
        if dest_path.exists() and dest_path.is_dir():
            dest_path = dest_path / src_path.name

        # Handle collisions
        if dest_path.exists() and not overwrite:
            dest_path = self._resolve_collision(dest_path)

        # Verify destination is inside root
        self._validate_destination(dest_path)

        # Ensure parent directories exist
        self._ensure_parent_dirs(dest_path)

        # Copy the file
        shutil.copy2(str(src_path), str(dest_path))

        return {
            "action": "copy_file",
            "source": str(self._get_relative(src_path)),
            "destination": str(self._get_relative(dest_path)),
            "success": True,
        }

    # ------------------------------------------------------------------
    # rename_file
    # ------------------------------------------------------------------

    def _rename_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Rename a file.

        Arguments:
            path: File path (relative to Fox root or absolute)
            new_name: New filename (NOT a path - just the name)

        Returns structured result.
        """
        path = arguments.get("path")
        new_name = arguments.get("new_name")

        if path is None or new_name is None:
            raise FoxSecurityError("rename_file requires 'path' and 'new_name' arguments")

        # Validate source (must exist)
        src_path = self._validate_source(path)

        if not src_path.is_file():
            raise FoxSecurityError(f"Path is not a file: {src_path}")

        # Skip if source is in trash
        if self._is_trash(src_path):
            raise FoxSecurityError("Cannot rename files in trash directly; use restore_file")

        # Validate new name (filename only, not a path)
        validated_name = self._validate_new_name(new_name)

        # Build destination path
        dest_path = src_path.parent / validated_name

        # Handle collisions
        dest_path = self._resolve_collision(dest_path)

        # Verify destination is inside root
        self._validate_destination(dest_path)

        # Rename the file
        src_path.rename(dest_path)

        return {
            "action": "rename_file",
            "original": str(self._get_relative(src_path)),
            "new_name": validated_name,
            "new_path": str(self._get_relative(dest_path)),
            "success": True,
        }

    # ------------------------------------------------------------------
    # create_folder
    # ------------------------------------------------------------------

    def _create_folder(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Create a directory.

        Arguments:
            path: Directory path (relative to Fox root or absolute)
            parents: If True, create parent directories (default: True)

        Returns structured result.
        """
        path = arguments.get("path")
        parents = arguments.get("parents", True)

        if path is None:
            raise FoxSecurityError("create_folder requires 'path' argument")

        # Validate destination
        dest_path = self._validate_destination(path, allow_new=True)

        # Create the directory
        if parents:
            dest_path.mkdir(parents=True, exist_ok=True)
        else:
            dest_path.mkdir(exist_ok=True)

        return {
            "action": "create_folder",
            "path": str(self._get_relative(dest_path)),
            "success": True,
        }

    # ------------------------------------------------------------------
    # delete_file (moves to trash)
    # ------------------------------------------------------------------

    def _delete_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Move a file to trash (not permanent delete).

        Arguments:
            path: File path (relative to Fox root or absolute)

        Returns structured result with trash location.
        """
        path = arguments.get("path")

        if path is None:
            raise FoxSecurityError("delete_file requires 'path' argument")

        # Validate source (must exist)
        src_path = self._validate_source(path)

        if not src_path.is_file():
            raise FoxSecurityError(f"Path is not a file: {src_path}")

        # Skip if already in trash
        if self._is_trash(src_path):
            raise FoxSecurityError("File is already in trash")

        # Build trash destination
        rel_path = self._get_relative(src_path)
        trash_path = self._boundary.trash_dir / rel_path

        # Ensure trash subdirectories exist
        self._ensure_parent_dirs(trash_path)

        # Handle collisions in trash
        trash_path = self._resolve_collision(trash_path)

        # Move to trash
        shutil.move(str(src_path), str(trash_path))

        return {
            "action": "delete_file",
            "original": str(rel_path),
            "trash_path": str(self._get_relative(trash_path)),
            "trashed": True,
        }

    # ------------------------------------------------------------------
    # search_files
    # ------------------------------------------------------------------

    def _search_files(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Search for files within Fox root.

        Arguments:
            query: Search query (substring match on filename)
            recursive: If True, search recursively (default: True)
            include_trash: If True, include trash in results (default: False)
            limit: Maximum results (default: 100)

        Returns structured result.
        """
        query = arguments.get("query", "").strip().lower()
        recursive = arguments.get("recursive", True)
        include_trash = arguments.get("include_trash", False)
        limit = arguments.get("limit", 100)

        if not query:
            return {
                "action": "search_files",
                "query": "",
                "results": [],
                "count": 0,
                "summary": "Empty query - no results.",
            }

        results: list[dict[str, Any]] = []

        if recursive:
            paths = self._target.rglob("*")
        else:
            paths = self._target.iterdir()

        for path in paths:
            # Skip trash unless explicitly included
            if not include_trash and self._is_trash(path):
                continue

            # Skip directories
            if not path.is_file():
                continue

            # Validate path is inside root
            try:
                self._validate_source(path)
            except FoxSecurityError:
                continue

            # Match query against filename
            if query in path.name.lower():
                rel = path.relative_to(self._target)
                results.append({
                    "path": str(rel),
                    "name": path.name,
                    "size": path.stat().st_size,
                    "modified": path.stat().st_mtime,
                })

                if len(results) >= limit:
                    break

        return {
            "action": "search_files",
            "query": query,
            "results": results,
            "count": len(results),
            "summary": f"Found {len(results)} file(s) matching '{query}'",
        }

    # ------------------------------------------------------------------
    # restore_file
    # ------------------------------------------------------------------

    def _restore_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Restore a file from trash to its original location or a new location.

        Arguments:
            path: Path in trash (relative to Fox root or absolute)
            destination: Optional destination path (default: original location)

        Returns structured result.
        """
        path = arguments.get("path")
        destination = arguments.get("destination")

        if path is None:
            raise FoxSecurityError("restore_file requires 'path' argument")

        # Validate source (must exist and be in trash)
        src_path = self._validate_source(path)

        if not self._is_trash(src_path):
            raise FoxSecurityError(f"Path is not in trash: {src_path}")

        # Determine destination
        if destination:
            dest_path = self._validate_destination(destination, allow_new=True)
            if dest_path.exists() and dest_path.is_dir():
                dest_path = dest_path / src_path.name
        else:
            # Try to restore to original location (strip trash prefix)
            rel = src_path.relative_to(self._boundary.trash_dir)
            dest_path = self._target / rel

        # Handle collisions
        if dest_path.exists():
            dest_path = self._resolve_collision(dest_path)

        # Ensure parent directories exist
        self._ensure_parent_dirs(dest_path)

        # Move from trash
        shutil.move(str(src_path), str(dest_path))

        return {
            "action": "restore_file",
            "trash_path": str(self._get_relative(src_path)),
            "restored_to": str(self._get_relative(dest_path)),
            "success": True,
        }

    # ------------------------------------------------------------------
    # empty_trash
    # ------------------------------------------------------------------

    def _empty_trash(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Permanently delete all files in trash.

        Arguments:
            confirm: Must be True to confirm (default: False)

        Returns structured result.
        """
        confirm = arguments.get("confirm", False)

        if not confirm:
            return {
                "action": "empty_trash",
                "success": False,
                "error": "Confirmation required: pass confirm=true",
            }

        deleted_count = 0
        for path in self._boundary.trash_dir.rglob("*"):
            if path.is_file():
                path.unlink()
                deleted_count += 1

        # Remove empty directories
        for path in sorted(self._boundary.trash_dir.rglob("*"), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()

        return {
            "action": "empty_trash",
            "deleted_count": deleted_count,
            "success": True,
        }