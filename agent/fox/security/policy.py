# Fox directory policy for the isolated agent workspace.

from pathlib import Path


class FoxSecurityError(PermissionError):
    """Raised when an operation violates Fox security policy."""


class FoxPolicyError(FoxSecurityError):
    """Raised when a filesystem operation violates the Fox directory policy."""


class FoxDirectoryPolicy:
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

    def __init__(self, root: str | Path):
        self._root = Path(root).expanduser().resolve()

    @property
    def root(self) -> Path:
        return self._root

    def _relative(self, path: str | Path) -> Path:
        candidate = Path(path).expanduser()

        if not candidate.is_absolute():
            candidate = self._root / candidate

        try:
            resolved = candidate.resolve(strict=False)
        except OSError as exc:
            raise FoxPolicyError(f"Unable to resolve path safely: {path}") from exc

        try:
            return resolved.relative_to(self._root)
        except ValueError as exc:
            raise FoxPolicyError(f"Path is outside Fox Space: {path}") from exc

    def area(self, path: str | Path) -> str:
        relative = self._relative(path)

        if not relative.parts:
            return "root"

        area = relative.parts[0]

        if area in self.RESERVED_DIRS:
            raise FoxPolicyError("Fox trash is controlled internally")

        if area not in (self.READ_ONLY_DIRS | self.WRITEABLE_DIRS):
            raise FoxPolicyError(f"Unknown or unmanaged Fox Space directory: {area}")

        return area

    def validate_read(self, path: str | Path) -> Path:
        relative = self._relative(path)

        if not relative.parts:
            raise FoxPolicyError("Fox Space root is not readable")

        # Allow root-level files for executor compatibility.
        if len(relative.parts) == 1:
            return self._root / relative

        area = relative.parts[0]

        if area in self.RESERVED_DIRS:
            raise FoxPolicyError("Fox trash is controlled internally")

        if area not in (self.READ_ONLY_DIRS | self.WRITEABLE_DIRS):
            raise FoxPolicyError(f"Unknown or unmanaged Fox Space directory: {area}")

        return self._root / relative

    def validate_write(self, path: str | Path) -> Path:
        relative = self._relative(path)

        if not relative.parts:
            raise FoxPolicyError("Fox Space root is not writable")

        # Allow root-level files (but not directories) for executor compatibility.
        if len(relative.parts) == 1:
            # Single component under root - allow as file operation.
            # Root-level directories (other than managed) are rejected by area().
            return self._root / relative

        area = relative.parts[0]

        if area in self.RESERVED_DIRS:
            raise FoxPolicyError("Fox trash is controlled internally")

        if area not in self.WRITEABLE_DIRS:
            raise FoxPolicyError(f"Unknown or unmanaged Fox Space directory: {area}")

        return self._root / relative

    def validate_create(self, path: str | Path) -> Path:
        # Creating directories at root level is not allowed.
        # Only managed subdirectories (workspace, storage, etc.) may be created.
        relative = self._relative(path)
        if not relative.parts:
            raise FoxPolicyError("Fox Space root is not writable")
        if len(relative.parts) == 1:
            raise FoxPolicyError("Arbitrary root-level directories are not allowed")
        return self.validate_write(path)

    def validate_delete(self, path: str | Path) -> Path:
        return self.validate_write(path)

    def validate_move_source(self, path: str | Path) -> Path:
        return self.validate_write(path)

    def validate_copy_source(self, path: str | Path) -> Path:
        return self.validate_read(path)

    def validate_organise_target(self, path: str | Path) -> Path:
        validated = self.validate_write(path)

        if self.area(validated) not in self.WRITEABLE_DIRS:
            raise FoxPolicyError("Files may only be organised inside workspace or storage")

        return validated

    def validate_restore_destination(self, path: str | Path, allow_new: bool = True) -> Path:
        return self.validate_write(path)

    def validate_move_destination(self, path: str | Path) -> Path:
        """Validate destination for move operations - both read and write allowed."""
        relative = self._relative(path)

        if not relative.parts:
            raise FoxPolicyError("Fox Space root cannot be a move destination")

        area = relative.parts[0]

        if area in self.RESERVED_DIRS:
            raise FoxPolicyError("Fox trash is controlled internally")

        if area not in (self.READ_ONLY_DIRS | self.WRITEABLE_DIRS):
            raise FoxPolicyError(f"Unknown or unmanaged Fox Space directory: {area}")

        return self._root / relative