# this program is going to handle the connection between phone and my pc!

# import the nessary modules
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

# this class raise error when kde connect can't perform an operation
class KDEConnectError(RuntimeError):
    ...

@dataclass
class KDEConnectBridge:
    binary: str = "kdeconnect"

    def _run(self, *args:str):
        if shutil.which(self.binary) is None:
            raise KDEConnectError(f"KDE Connect Cli {self.binary} was not found.")

        
        try:
            result = subprocess.run([self.binary, *args], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise KDEConnectError(e.stderr.strip() or f"KDE Connect command failed: {' '.join(args)}") from e
        return result.stdout.strip()

    def version(self):
        return self._run("--version")

    def list_devices(self):
        return self._run("--list-devices")

    def list_available(self):
        return self._run("--list-available")

    def refresh(self):
        return self._run("--refresh")

    def encryption_info(self, device: str | None = None):
        args = ["--encryption-info"]

        if device:
            args.extend(["--device"], device)

        return self._run(*args)

    