# Minimal file-management executor for the Fox Club Runtime.
# Adapts Selina's ActionExecutor protocol to work on a user-supplied
# target directory, using File_Manager/preferences for categorisation.

import shutil
from pathlib import Path
from typing import Any

from File_Manager import preferences

# Reuse the canonical category list from the existing organizer.
CATEGORIES = ["Documents", "Notes", "Code", "Images", "Audio", "Video", "Archives", "Other"]


class FileActionExecutor:
    """
    Satisfies Selina's ActionExecutor protocol.

    Scoped to a single target directory.  All paths must resolve inside
    that directory — path-traversal attempts are rejected.
    """

    def __init__(self, target_dir: Path):
        # Resolve to absolute so all containment checks are reliable.
        self._target = target_dir.resolve()

        # Create the target directory if it does not exist yet.
        self._target.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Path safety
    # ------------------------------------------------------------------

    def _assert_inside(self, path: Path) -> Path:
        """Return the resolved path or raise if it escapes the target."""
        resolved = path.resolve()
        if not (resolved == self._target or str(resolved).startswith(str(self._target) + "/")):
            raise PermissionError(
                f"[FileActionExecutor]: Path escapes the target directory: {path}"
            )
        return resolved

    # ------------------------------------------------------------------
    # ActionExecutor protocol
    # ------------------------------------------------------------------

    def execute(self, action: str, arguments: dict[str, Any]) -> Any:
        action = action.strip().lower().replace(" ", "_")

        if action == "organise_folder":
            return self._organise_folder(arguments)

        raise RuntimeError(
            f"[FileActionExecutor]: Unknown action '{action}'. "
            f"Supported: organise_folder"
        )

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

            # Verify the source file is inside the target directory.
            self._assert_inside(entry)

            ext = entry.suffix.lower()
            category = preferences.category_for(ext)

            dest_dir = self._target / category
            dest_dir.mkdir(parents=True, exist_ok=True)

            dest_path = dest_dir / entry.name

            # Handle duplicate filenames inside the category folder.
            counter = 1
            while dest_path.exists():
                dest_path = dest_dir / f"{entry.stem}_{counter}{entry.suffix}"
                counter += 1

            # Verify the destination is inside the target directory.
            self._assert_inside(dest_path)

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
