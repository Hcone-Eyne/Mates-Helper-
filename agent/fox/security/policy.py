# Fox directory policy for the isolated agent workspace.

from pathlib import Path


class FoxPolicyError(PermissionError):
    """Raised when a filesystem operation violates the Fox policy."""


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

        area = relative.parts[0]

        if area in self.RESERVED_DIRS:
            raise FoxPolicyError("Fox trash is controlled internally")

        if area not in (self.READ_ONLY_DIRS | self.WRITEABLE_DIRS):
            raise FoxPolicyError(f"Unknown or unmanaged Fox Space directory: {area}")

        return Path(path).expanduser().resolve(strict=False)

    def validate_write(self, path: str | Path) -> Path:
        relative = self._relative(path)

        if not relative.parts:
            raise FoxPolicyError("Fox Space root is not writable")

        area = relative.parts[0]

        if area in self.RESERVED_DIRS:
            raise FoxPolicyError("Fox trash is controlled internally")

        if area not in self.WRITEABLE_DIRS:
            raise FoxPolicyError(f"Unknown or unmanaged Fox Space directory: {area}")

        return Path(path).expanduser().resolve(strict=False)

    def validate_create(self, path: str | Path) -> Path:
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

    def validate_restore_destination(self, path: str | Path) -> Path:
        return self.validate_write(path)