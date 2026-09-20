from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


class KDEConnectError(RuntimeError):
    """Raised when KDE Connect cannot perform an operation."""


@dataclass
class KDEConnectBridge:
    """
    Isolated interface between Phone Hub and KDE Connect.

    Fox must NOT import or use this class directly.
    """

    binary: str = "kdeconnect"

    def _run(self, *args: str) -> str:
        if shutil.which(self.binary) is None:
            raise KDEConnectError(
                f"KDE Connect CLI '{self.binary}' was not found."
            )

        try:
            result = subprocess.run(
                [self.binary, *args],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip()

            raise KDEConnectError(
                message or
                f"KDE Connect command failed: {' '.join(args)}"
            ) from exc

        return result.stdout.strip()

    def version(self) -> str:
        return self._run("--version")

    def list_devices(self) -> str:
        return self._run("--list-devices")

    def list_available(self) -> str:
        return self._run("--list-available")

    def refresh(self) -> str:
        return self._run("--refresh")

    def encryption_info(self, device: str | None = None) -> str:
        args = ["--encryption-info"]

        if device:
            args.extend(["--device", device])

        return self._run(*args)

    def ping(self, device: str | None = None) -> str:
        args = ["--ping"]

        if device:
            args.extend(["--device", device])

        return self._run(*args)

    def share(self, path: str, device: str | None = None) -> str:
        args = ["--share", path]

        if device:
            args.extend(["--device", device])

        return self._run(*args)

    def share_text(
        self,
        text: str,
        device: str | None = None,
    ) -> str:
        args = ["--share-text", text]

        if device:
            args.extend(["--device", device])

        return self._run(*args)