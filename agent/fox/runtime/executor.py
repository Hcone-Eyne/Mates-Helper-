# Adapts Selina's ActionExecutor protocol to work with FoxSecurityBoundary
# All filesystem operations are constrained by FoxSecurityBoundary
# LLMs can request actions but cannot authorize privileged operations

import shutil
from pathlib import Path
from typing import Any, Union

from File_Manager import preferences
from agent.fox.security import (
    FoxSecurityBoundary,
    FoxSecurityError,
    InvalidActionError,
    StorageQuotaError,
)


CATEGORIES = [
    "Documents",
    "Notes",
    "Code",
    "Images",
    "Audio",
    "Video",
    "Archives",
    "Other",
]


class FileActionExecutor:
    """
    File executor constrained by FoxSecurityBoundary.

    The boundary is the security authority.

    Important:
        empty_trash is privileged.
        Normal LLM action arguments cannot authorize it.
    """

    def __init__(
        self,
        boundary: Union[FoxSecurityBoundary, Path, str],
    ):
        if isinstance(boundary, FoxSecurityBoundary):
            self._boundary = boundary
        else:
            self._boundary = FoxSecurityBoundary(boundary)

        self._target = self._boundary.root_resolved

    # ------------------------------------------------------------------
    # Backward compatibility
    # ------------------------------------------------------------------

    def _assert_inside(self, path: Path) -> Path:
        try:
            return self._boundary.validate_source_path(path)
        except FoxSecurityError as exc:
            raise PermissionError(
                f"Path escapes the target directory: {path}"
            ) from exc

    # ------------------------------------------------------------------
    # Public execution
    # ------------------------------------------------------------------

    def execute(
        self,
        action: str,
        arguments: dict[str, Any],
    ) -> Any:
        try:
            canonical_action = self._boundary.validate_action(action)
        except InvalidActionError as exc:
            raise RuntimeError(
                f"Unknown action '{action}'. "
                f"Supported: "
                f"{', '.join(sorted(self._boundary.SUPPORTED_ACTIONS))}"
            ) from exc

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
            f"Unknown action '{action}'"
        )

    # ------------------------------------------------------------------
    # Security helpers
    # ------------------------------------------------------------------

    def _validate_source(self, path: str | Path) -> Path:
        return self._boundary.validate_source_path(path)

    def _validate_destination(
        self,
        path: str | Path,
        allow_new: bool = True,
    ) -> Path:
        return self._boundary.validate_destination_path(
            path,
            allow_new=allow_new,
        )

    def _validate_read(self, path: str | Path) -> Path:
        return self._boundary.validate_read(path)

    def _validate_write(self, path: str | Path) -> Path:
        return self._boundary.validate_write(path)

    def _check_quota_for_write(self, source: Path, dest: Path, operation: str) -> None:
        """Check storage quota for a write operation."""
        try:
            self._boundary.check_storage_quota_for_write(source, dest, operation)
        except StorageQuotaError as e:
            raise RuntimeError(f"Storage quota exceeded: {e}") from e

    def _validate_new_name(self, name: str) -> str:
        return self._boundary.validate_new_name(name)

    def _ensure_parent_dirs(self, path: Path) -> Path:
        return self._boundary.ensure_parent_dirs(path)

    def _get_relative(self, path: Path) -> Path:
        return self._boundary.get_relative_path(path)

    def _is_trash(self, path: Path) -> bool:
        return self._boundary.is_trash_path(path)

    def _resolve_collision(self, dest_path: Path) -> Path:
        """
        Resolve filename collision.

        Every candidate remains constrained to Fox root.
        """

        dest_path = self._validate_destination(
            dest_path,
            allow_new=True,
        )

        if not dest_path.exists():
            return dest_path

        counter = 1
        stem = dest_path.stem
        suffix = dest_path.suffix
        parent = dest_path.parent

        self._validate_destination(parent, allow_new=True)

        while True:
            candidate = parent / f"{stem}_{counter}{suffix}"

            self._validate_destination(
                candidate,
                allow_new=True,
            )

            if not candidate.exists():
                return candidate

            counter += 1

    # ------------------------------------------------------------------
    # organise_folder
    # ------------------------------------------------------------------

    def _organise_folder(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        moved: dict[str, list[str]] = {
            category: []
            for category in CATEGORIES
        }

        # Validate target itself before scanning.
        self._validate_source(self._target)

        for entry in sorted(self._target.iterdir()):

            if self._is_trash(entry):
                continue

            if not entry.is_file():
                continue

            src = self._validate_source(entry)

            extension = src.suffix.lower()
            category = preferences.category_for(extension)

            dest_dir = self._target / category

            self._validate_destination(
                dest_dir,
                allow_new=True,
            )

            dest_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            # Revalidate after directory creation.
            self._validate_destination(
                dest_dir,
                allow_new=True,
            )

            dest_path = dest_dir / src.name

            dest_path = self._resolve_collision(
                dest_path
            )

            self._validate_destination(
                dest_path,
                allow_new=True,
            )

            shutil.move(
                str(src),
                str(dest_path),
            )

            moved[category].append(src.name)

        summary_parts: list[str] = []

        for category in CATEGORIES:
            files = moved[category]

            if files:
                summary_parts.append(
                    f"{category}: {', '.join(files)}"
                )

        return {
            "target": str(self._target),
            "moved": {
                category: files
                for category, files in moved.items()
                if files
            },
            "summary": (
                "; ".join(summary_parts)
                if summary_parts
                else "No files to organise."
            ),
        }

    # ------------------------------------------------------------------
    # list_directory
    # ------------------------------------------------------------------

    def _list_directory(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        recursive = bool(
            arguments.get("recursive", False)
        )

        # Trash is deliberately hidden from normal Fox views.
        show_trash = bool(
            arguments.get("show_trash", False)
        )

        self._validate_source(self._target)

        entries: list[str] = []

        paths = (
            self._target.rglob("*")
            if recursive
            else self._target.iterdir()
        )

        for path in sorted(paths):

            if not show_trash and self._is_trash(path):
                continue

            validated = self._validate_source(path)

            rel = validated.relative_to(
                self._target
            )

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

    def _move_file(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        source = arguments.get("source")
        destination = arguments.get("destination")
        overwrite = bool(
            arguments.get("overwrite", False)
        )

        if source is None or destination is None:
            raise FoxSecurityError(
                "move_file requires "
                "'source' and 'destination'"
            )

        src_path = self._boundary.validate_move_source(source)

        if not src_path.is_file():
            raise FoxSecurityError(
                f"Source is not a file: {src_path}"
            )

        if self._is_trash(src_path):
            raise FoxSecurityError(
                "Cannot move files from trash directly; "
                "use restore_file"
            )

        dest_path = self._boundary.validate_move_destination(destination)

        if dest_path.exists() and dest_path.is_dir():
            dest_path = dest_path / src_path.name

        if dest_path.exists() and not overwrite:
            dest_path = self._resolve_collision(
                dest_path
            )

        # Check storage quota before moving
        self._check_quota_for_write(src_path, dest_path, "move")

        self._boundary.validate_write(dest_path)

        self._ensure_parent_dirs(dest_path)

        shutil.move(
            str(src_path),
            str(dest_path),
        )

        return {
            "action": "move_file",
            "source": str(
                self._get_relative(src_path)
            ),
            "destination": str(
                self._get_relative(dest_path)
            ),
            "success": True,
        }

    # ------------------------------------------------------------------
    # copy_file
    # ------------------------------------------------------------------

    def _copy_file(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        source = arguments.get("source")
        destination = arguments.get("destination")
        overwrite = bool(
            arguments.get("overwrite", False)
        )

        if source is None or destination is None:
            raise FoxSecurityError(
                "copy_file requires "
                "'source' and 'destination'"
            )

        src_path = self._validate_read(source)

        if not src_path.is_file():
            raise FoxSecurityError(
                f"Source is not a file: {src_path}"
            )

        if self._is_trash(src_path):
            raise FoxSecurityError(
                "Cannot copy files from trash directly; "
                "use restore_file"
            )

        dest_path = self._validate_write(destination)

        if dest_path.exists() and dest_path.is_dir():
            dest_path = dest_path / src_path.name

        if dest_path.exists() and not overwrite:
            dest_path = self._resolve_collision(
                dest_path
            )

        # Check storage quota before copying (copy increases usage)
        self._check_quota_for_write(src_path, dest_path, "copy")

        self._validate_write(dest_path)

        self._ensure_parent_dirs(dest_path)

        shutil.copy2(
            str(src_path),
            str(dest_path),
        )

        return {
            "action": "copy_file",
            "source": str(
                self._get_relative(src_path)
            ),
            "destination": str(
                self._get_relative(dest_path)
            ),
            "success": True,
        }

    # ------------------------------------------------------------------
    # rename_file
    # ------------------------------------------------------------------

    def _rename_file(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        path = arguments.get("path")
        new_name = arguments.get("new_name")

        if path is None or new_name is None:
            raise FoxSecurityError(
                "rename_file requires "
                "'path' and 'new_name'"
            )

        src_path = self._boundary.validate_rename_source(path)

        if not src_path.is_file():
            raise FoxSecurityError(
                f"Path is not a file: {src_path}"
            )

        if self._is_trash(src_path):
            raise FoxSecurityError(
                "Cannot rename files in trash directly; "
                "use restore_file"
            )

        validated_name = self._validate_new_name(
            new_name
        )

        dest_path = (
            src_path.parent / validated_name
        )

        dest_path = self._resolve_collision(
            dest_path
        )

        self._boundary.validate_rename_destination(dest_path)

        src_path.rename(dest_path)

        return {
            "action": "rename_file",
            "original": str(
                self._get_relative(src_path)
            ),
            "new_name": validated_name,
            "new_path": str(
                self._get_relative(dest_path)
            ),
            "success": True,
        }

    # ------------------------------------------------------------------
    # create_folder
    # ------------------------------------------------------------------

    def _create_folder(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        path = arguments.get("path")
        parents = bool(
            arguments.get("parents", True)
        )

        if path is None:
            raise FoxSecurityError(
                "create_folder requires 'path'"
            )

        dest_path = self._boundary.validate_create(path)

        # Check storage quota before creating folder
        self._check_quota_for_write(dest_path, dest_path, "create")

        if parents:
            dest_path.mkdir(
                parents=True,
                exist_ok=True,
            )
        else:
            dest_path.mkdir(
                exist_ok=True,
            )

        # Revalidate after creation.
        self._boundary.validate_write(dest_path)

        return {
            "action": "create_folder",
            "path": str(
                self._get_relative(dest_path)
            ),
            "success": True,
        }

    # ------------------------------------------------------------------
    # delete_file
    # ------------------------------------------------------------------

    def _delete_file(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        path = arguments.get("path")

        if path is None:
            raise FoxSecurityError(
                "delete_file requires 'path'"
            )

        src_path = self._boundary.validate_delete(path)

        if not src_path.is_file():
            raise FoxSecurityError(
                f"Path is not a file: {src_path}"
            )

        if self._is_trash(src_path):
            raise FoxSecurityError(
                "File is already in trash"
            )

        # Check storage quota (delete moves to trash, which is already counted)
        self._check_quota_for_write(src_path, src_path, "delete")

        rel_path = self._get_relative(src_path)

        trash_path = (
            self._boundary.trash_dir / rel_path
        )

        # Explicitly validate the generated trash path using trash-specific validation.
        self._boundary.validate_trash_write(trash_path)

        self._ensure_parent_dirs(
            trash_path
        )

        trash_path = self._resolve_collision(
            trash_path
        )

        # Revalidate after collision resolution.
        self._boundary.validate_trash_write(trash_path)

        shutil.move(
            str(src_path),
            str(trash_path),
        )

        return {
            "action": "delete_file",
            "original": str(rel_path),
            "trash_path": str(
                self._get_relative(trash_path)
            ),
            "trashed": True,
        }

    # ------------------------------------------------------------------
    # search_files
    # ------------------------------------------------------------------

    def _search_files(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        query = str(
            arguments.get("query", "")
        ).strip().lower()

        recursive = bool(
            arguments.get("recursive", True)
        )

        include_trash = bool(
            arguments.get("include_trash", False)
        )

        limit = arguments.get("limit", 100)

        if not isinstance(limit, int):
            raise FoxSecurityError(
                "search_files 'limit' must be an integer"
            )

        if limit < 1:
            raise FoxSecurityError(
                "search_files 'limit' must be >= 1"
            )

        if not query:
            return {
                "action": "search_files",
                "query": "",
                "results": [],
                "count": 0,
                "summary": (
                    "Empty query - no results."
                ),
            }

        results: list[dict[str, Any]] = []

        paths = (
            self._target.rglob("*")
            if recursive
            else self._target.iterdir()
        )

        for path in paths:

            if not include_trash and self._is_trash(path):
                continue

            if not path.is_file():
                continue

            try:
                validated = self._boundary.validate_read(path)
            except FoxSecurityError:
                # Fail closed for unexpected filesystem entries.
                continue

            if query not in validated.name.lower():
                continue

            stat = validated.stat()

            rel = validated.relative_to(
                self._target
            )

            results.append({
                "path": str(rel),
                "name": validated.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })

            if len(results) >= limit:
                break

        return {
            "action": "search_files",
            "query": query,
            "results": results,
            "count": len(results),
            "summary": (
                f"Found {len(results)} file(s) "
                f"matching '{query}'"
            ),
        }

    # ------------------------------------------------------------------
    # restore_file
    # ------------------------------------------------------------------

    def _restore_file(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        path = arguments.get("path")
        destination = arguments.get("destination")

        if path is None:
            raise FoxSecurityError(
                "restore_file requires 'path'"
            )

        src_path = self._boundary.validate_trash_path(
            path,
            must_exist=True,
        )

        if not src_path.is_file():
            raise FoxSecurityError(
                f"Trash path is not a file: {src_path}"
            )

        if destination is not None:
            dest_path = self._boundary.validate_restore_destination(destination)

            if (
                dest_path.exists()
                and dest_path.is_dir()
            ):
                dest_path = (
                    dest_path / src_path.name
                )

        else:
            rel = src_path.relative_to(
                self._boundary.trash_dir
            )

            dest_path = self._target / rel

        # Explicitly validate computed restore destination.
        dest_path = self._boundary.validate_restore_destination(
            dest_path,
            allow_new=True,
        )

        if dest_path.exists():
            dest_path = self._resolve_collision(
                dest_path
            )

        # Check storage quota (restore from trash doesn't increase total usage)
        self._check_quota_for_write(src_path, dest_path, "restore")

        self._boundary.validate_write(dest_path)

        self._ensure_parent_dirs(
            dest_path
        )

        shutil.move(
            str(src_path),
            str(dest_path),
        )

        return {
            "action": "restore_file",
            "trash_path": str(
                self._get_relative(src_path)
            ),
            "restored_to": str(
                self._get_relative(dest_path)
            ),
            "success": True,
        }

    # ------------------------------------------------------------------
    # empty_trash
    # ------------------------------------------------------------------

    def _empty_trash(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        """
        Permanently delete everything in Fox trash.

        SECURITY:
            This action cannot be authorized with:
                confirm=True

            It requires a trusted authorization token supplied by
            application code outside the LLM-generated arguments.

        Example trusted call:

            executor._empty_trash(
                {"authorization_token": boundary}
            )

        Normal LLM calls cannot manufacture this authorization because
        they do not receive the boundary object.
        """

        token = arguments.get(
            "authorization_token"
        )

        # The authorization object must be the actual boundary instance.
        self._boundary.authorize_privileged_action(
            "empty_trash",
            authorization_token=token,
        )

        deleted_count = 0

        # Validate trash root itself.
        trash_root = self._boundary.validate_trash_path(
            self._boundary.trash_dir,
            must_exist=True,
        )

        # Snapshot entries before deleting.
        entries = sorted(
            trash_root.rglob("*"),
            key=lambda path: len(path.parts),
            reverse=True,
        )

        for path in entries:
            # Every entry is independently validated.
            validated = self._boundary.validate_trash_path(
                path,
                must_exist=True,
            )

            if validated.is_file():
                validated.unlink()
                deleted_count += 1

            elif validated.is_dir():
                # Only remove after its children were processed.
                try:
                    validated.rmdir()
                except OSError:
                    # Non-empty directories are left alone.
                    pass

        return {
            "action": "empty_trash",
            "deleted_count": deleted_count,
            "success": True,
        }
