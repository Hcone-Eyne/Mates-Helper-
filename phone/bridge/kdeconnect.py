from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


class KDEConnectError(RuntimeError):
    """Raised when KDE Connect cannot perform an operation."""


def _find_kdeconnect_cli() -> str:
    """Find the kdeconnect-cli binary, checking standard locations."""
    # First check PATH (e.g., Homebrew install) - return base name for portability
    if shutil.which("kdeconnect-cli"):
        return "kdeconnect-cli"
    # Then check macOS app bundle location - use full path since it's not in PATH
    app_bundle = "/Applications/KDE Connect.app/Contents/MacOS/kdeconnect-cli"
    if os.path.isfile(app_bundle) and os.access(app_bundle, os.X_OK):
        return app_bundle
    # Fallback to kdeconnect (some installs use this name)
    if shutil.which("kdeconnect"):
        return "kdeconnect"
    return "kdeconnect-cli"


@dataclass
class KDEConnectBridge:
    """
    Isolated interface between Phone Hub and KDE Connect.

    Fox must NOT import or use this class directly.
    """

    binary: str = ""

    def __post_init__(self):
        if not self.binary:
            self.binary = _find_kdeconnect_cli()

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

            # Defensive: surface the common "No such object path" failure
            # which typically means the KDE Connect daemon isn't properly
            # connected to the device (mDNS/network binding issue), not a
            # problem with the CLI invocation itself.
            if "No such object path" in message:
                message = (
                    "KDE Connect daemon isn't responding — check the D-Bus "
                    "service registration and daemon health (mDNS/network "
                    "binding issue). Original error: " + message
                )

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