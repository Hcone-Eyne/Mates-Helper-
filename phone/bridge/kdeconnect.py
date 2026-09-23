from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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

    def list_notifications(self, device: str | None = None) -> str:
        """List notifications from the connected device."""
        args = ["--list-notifications"]

        if device:
            args.extend(["--device", device])

        return self._run(*args)

    def list_notifications_json(self, device: str | None = None) -> list[dict]:
        """List notifications from the connected device as parsed JSON."""
        # KDE Connect doesn't have a --json flag for --list-notifications yet
        # We'll need to parse the text output
        raw_output = self.list_notifications(device)
        return self._parse_notifications_output(raw_output)

    def _parse_notifications_output(self, output: str) -> list[dict]:
        """Parse KDE Connect --list-notifications text output into structured data.
        
        KDE Connect output format (approximate, varies by version):
        [
          {
            "id": "notification_id",
            "appName": "App Name",
            "packageName": "com.package.name",
            "title": "Notification title",
            "text": "Notification body text",
            "timestamp": 1234567890000,
            ...
          }
        ]
        Or plain text format if JSON not available.
        """
        output = output.strip()
        if not output:
            return []

        # Try to parse as JSON first (newer KDE Connect versions)
        try:
            data = json.loads(output)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

        # Fallback: parse plain text format (older versions or fallback)
        # This is a best-effort parsing - format may vary
        notifications = []
        lines = output.strip().split('\n')
        current = {}
        for line in lines:
            line = line.strip()
            if not line:
                if current:
                    notifications.append(current)
                    current = {}
                continue
            
            if ':' in line:
                key, value = line.split(':', 1)
                current[key.strip()] = value.strip()
        
        if current:
            notifications.append(current)
        
        return notifications

    def get_notifications(self, device: str | None = None) -> list[dict]:
        """Get parsed notifications from the device.
        
        This is a higher-level method that handles parsing and returns
        structured notification data. Returns empty list if device
        is not connected or has no notifications.
        """
        try:
            return self.list_notifications_json(device)
        except Exception:
            # Device not connected, no notifications, or parse error
            return []

    def send_sms(self, destination: str, message: str, device: str | None = None) -> str:
        """Send an SMS message via KDE Connect.
        
        Args:
            destination: Phone number to send SMS to
            message: Message text to send
            device: Target device ID
            
        Returns:
            Success message from KDE Connect
        """
        args = ["--send-sms", message]
        
        if destination:
            args.extend(["--destination", destination])
        
        if device:
            args.extend(["--device", device])
        
        return self._run(*args)

    def list_sms(self, device: str | None = None) -> str:
        """List SMS messages from the device.
        
        Note: KDE Connect's SMS functionality may be limited
        depending on the device and Android version.
        """
        # KDE Connect doesn't have a direct --list-sms command
        # This is a placeholder for future implementation
        return "SMS listing not yet supported by KDE Connect CLI"