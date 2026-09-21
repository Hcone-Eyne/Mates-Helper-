# this acts like blocker to fox club to prevent accessing the personal context

# importing the nessaery modules..
from pathlib import Path
from enum import Enum

class SecurityDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"

class SecurityViolation(PermissionError):
    ''' Activates when an query violates the Security Rules....'''

class NoHeartSecurity:

    READ_ONLY = frozenset({
        "system",
        "apps",
        "config"
    })

    WRITEABLE = frozenset({ "workspace", "storage"})

    SUPPORTED_ACTIONS = frozenset({
        "list_directory",
        "search_folder",
        "move_file",
        "copy_file",
        "rename_file",
        "delete_file",
        "restore_file",
        "organise_folder"
    })

    def __init__(self, root: str | Path):
        set.root = Path(root).resolve()

    @property
    def root(self):
        return self._root

    def _resolve(self, path:str | Path):
        return Path(path).resolve(strict = False)

    def _inside_root(self, path:Path):
        try:
            path.relative_to(self._root)
            return True
        except ValueError:
            return False

    def _area(self, path:Path):
        try: 
            relative = path.relative_to(self._root)
        except ValueError:
            return None

        return relative.parts[0]

    def validate_path(self, path: str | Path) -> Path:
        candidate = self._resolve(path)

        if not self._inside_root(candidate):
            raise SecurityViolation(
                f"DENIED: path outside Fox Space: {path}"
            )

        area = self._area(candidate)

        if area in self.RESERVED:
            raise SecurityViolation(
                "DENIED: reserved Fox security area"
            )

        if area not in self.READ_ONLY | self.WRITABLE:
            raise SecurityViolation(
                f"DENIED: unmanaged Fox Space area: {area}"
            )

        return candidate

    # ---------------------------------------------------------
    # READ
    # ---------------------------------------------------------

    def allow_read(self, path: str | Path) -> bool:
        self.validate_path(path)
        return True

    # ---------------------------------------------------------
    # WRITE
    # ---------------------------------------------------------

    def allow_write(self, path: str | Path) -> bool:
        candidate = self.validate_path(path)
        area = self._area(candidate)

        if area not in self.WRITABLE:
            raise SecurityViolation(
                f"DENIED: {area}/ is read-only"
            )

        return True

    # ---------------------------------------------------------
    # ACTION
    # ---------------------------------------------------------

    def authorize(
        self,
        action: str,
        source: str | Path | None = None,
        destination: str | Path | None = None,
    ) -> SecurityDecision:

        if action not in self.SUPPORTED_ACTIONS:
            raise SecurityViolation(
                f"DENIED: unsupported action: {action}"
            )

        # READ operations
        if action in {
            "list_directory",
            "search_files",
        }:
            if source is None:
                raise SecurityViolation(
                    "DENIED: source path required"
                )

            self.allow_read(source)
            return SecurityDecision.ALLOW

        # CREATE
        if action == "create_folder":
            if destination is None:
                raise SecurityViolation(
                    "DENIED: destination required"
                )

            self.allow_write(destination)
            return SecurityDecision.ALLOW

        # COPY
        if action == "copy_file":
            if source is None or destination is None:
                raise SecurityViolation(
                    "DENIED: source and destination required"
                )

            # Reading from system/apps/config is allowed.
            self.allow_read(source)

            # Writing there is not.
            self.allow_write(destination)

            return SecurityDecision.ALLOW

        # MOVE / RENAME / DELETE
        if action in {
            "move_file",
            "rename_file",
            "delete_file",
            "organise_folder",
        }:
            target = source or destination

            if target is None:
                raise SecurityViolation(
                    "DENIED: target path required"
                )

            self.allow_write(target)

            if action == "move_file":
                if destination is None:
                    raise SecurityViolation(
                        "DENIED: destination required"
                    )

                self.allow_write(destination)

            return SecurityDecision.ALLOW

        # RESTORE
        if action == "restore_file":
            if destination is None:
                raise SecurityViolation(
                    "DENIED: restore destination required"
                )

            self.allow_write(destination)
            return SecurityDecision.ALLOW

        raise SecurityViolation(
            f"DENIED: no security rule for action: {action}"
        )


__all__ = [
    "NoHeartSecurity",
    "SecurityDecision",
    "SecurityViolation",
]