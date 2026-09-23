"""Tests for Phone Hub CLI (phone.phone_cli.phone_cli)."""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock, call
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from phone.bridge.kdeconnect import KDEConnectBridge, KDEConnectError
from phone.phone_cli.phone_cli import main


class MockBridge:
    """Mock KDEConnectBridge for testing CLI without subprocess."""

    def __init__(self):
        self.calls = []

    def version(self):
        self.calls.append(("version", ()))
        return "kdeconnect-cli 26.08.1"

    def list_devices(self):
        self.calls.append(("list_devices", ()))
        return "- POCO C71: 8599f9fc623f4dcbb097f80488529359 on 10.20.86.55 via LAN (paired and reachable)\n1 device found"

    def list_available(self):
        self.calls.append(("list_available", ()))
        return "- POCO C71: 8599f9fc623f4dcbb097f80488529359 on 10.20.86.55 via LAN (paired and reachable)\n1 device found"

    def refresh(self):
        self.calls.append(("refresh", ()))
        return "Refreshed"

    def encryption_info(self, device=None):
        self.calls.append(("encryption_info", (device,)))
        if device is None:
            raise KDEConnectError("No device specified")
        return "SHA256 fingerprint of your device certificate is: 1f:a5:d3:ed:54:a9:38:85:bb:fe:8c:5a:3a:d1:b4:3f:0f:fb:cd:fc:34:27:49:d9:05:ca:2b:d6:ca:44:0b:a1\nSHA256 fingerprint of remote device certificate is: e3:63:43:19:87:c3:e9:ae:f0:16:a5:46:89:0a:25:d4:cf:10:54:52:bd:b9:35:ca:be:2a:ca:62:23:21:bc:c2\nProtocol version: 8"

    def ping(self, device=None):
        self.calls.append(("ping", (device,)))
        if device is None:
            raise KDEConnectError("No device specified")
        return ""

    def share(self, path, device=None):
        self.calls.append(("share", (path, device)))
        if device is None:
            raise KDEConnectError("No device specified")
        return f"Shared file://{path}"

    def share_text(self, text, device=None):
        self.calls.append(("share_text", (text, device)))
        if device is None:
            raise KDEConnectError("No device specified")
        return f"Shared text: {text}"


class FailingBridge(MockBridge):
    """Mock bridge that raises KDEConnectError on all calls."""

    def __init__(self, error_msg="KDE Connect command failed"):
        super().__init__()
        self.error_msg = error_msg

    def version(self):
        self.calls.append(("version", ()))
        raise KDEConnectError(self.error_msg)

    def list_devices(self):
        self.calls.append(("list_devices", ()))
        raise KDEConnectError(self.error_msg)

    def list_available(self):
        self.calls.append(("list_available", ()))
        raise KDEConnectError(self.error_msg)

    def refresh(self):
        self.calls.append(("refresh", ()))
        raise KDEConnectError(self.error_msg)

    def encryption_info(self, device=None):
        self.calls.append(("encryption_info", (device,)))
        raise KDEConnectError(self.error_msg)

    def ping(self, device=None):
        self.calls.append(("ping", (device,)))
        raise KDEConnectError(self.error_msg)

    def share(self, path, device=None):
        self.calls.append(("share", (path, device)))
        raise KDEConnectError(self.error_msg)

    def share_text(self, text, device=None):
        self.calls.append(("share_text", (text, device)))
        raise KDEConnectError(self.error_msg)

    def send_sms(self, destination, message, device=None):
        self.calls.append(("send_sms", (destination, message, device)))
        raise KDEConnectError(self.error_msg)


class MissingBinaryBridge(MockBridge):
    """Mock bridge that simulates missing KDE Connect binary."""

    def version(self):
        raise KDEConnectError("KDE Connect CLI 'kdeconnect' was not found.")

    def list_devices(self):
        raise KDEConnectError("KDE Connect CLI 'kdeconnect' was not found.")

    def list_available(self):
        raise KDEConnectError("KDE Connect CLI 'kdeconnect' was not found.")

    def refresh(self):
        raise KDEConnectError("KDE Connect CLI 'kdeconnect' was not found.")

    def encryption_info(self, device=None):
        raise KDEConnectError("KDE Connect CLI 'kdeconnect' was not found.")

    def ping(self, device=None):
        raise KDEConnectError("KDE Connect CLI 'kdeconnect' was not found.")

    def share(self, path, device=None):
        raise KDEConnectError("KDE Connect CLI 'kdeconnect' was not found.")

    def share_text(self, text, device=None):
        raise KDEConnectError("KDE Connect CLI 'kdeconnect' was not found.")

    def send_sms(self, destination, message, device=None):
        raise KDEConnectError("KDE Connect CLI 'kdeconnect' was not found.")


def run_cli(args, bridge=None):
    """Run the CLI main with given args and optional mock bridge."""
    if bridge is None:
        bridge = MockBridge()

    with patch("phone.phone_cli.phone_cli.KDEConnectBridge", return_value=bridge):
        with patch("sys.argv", ["fox-phone"] + args):
            with patch("sys.stdout", new=MagicMock()) as mock_stdout:
                with patch("sys.stderr", new=MagicMock()) as mock_stderr:
                    try:
                        main()
                        exit_code = 0
                    except SystemExit as e:
                        exit_code = e.code
                    stdout = "".join(str(c) for c in mock_stdout.write.call_args_list) if mock_stdout.write.called else ""
                    stderr = "".join(str(c) for c in mock_stderr.write.call_args_list) if mock_stderr.write.called else ""
                    return exit_code, stdout, stderr


def run_cli_raw(args, bridge=None):
    """Run CLI and capture actual print output."""
    if bridge is None:
        bridge = MockBridge()

    with patch("phone.phone_cli.phone_cli.KDEConnectBridge", return_value=bridge):
        with patch("sys.argv", ["fox-phone"] + args):
            with patch("sys.stdout", new=MagicMock()) as mock_stdout:
                with patch("sys.stderr", new=MagicMock()) as mock_stderr:
                    try:
                        main()
                        exit_code = 0
                    except SystemExit as e:
                        exit_code = e.code
                    stdout_calls = [str(c[0][0]) for c in mock_stdout.write.call_args_list] if mock_stdout.write.called else []
                    stderr_calls = [str(c[0][0]) for c in mock_stderr.write.call_args_list] if mock_stderr.write.called else []
                    return exit_code, "".join(stdout_calls), "".join(stderr_calls)


class TestStatusCommand:
    """Test 'status' command."""

    def test_status_success(self):
        exit_code, stdout, stderr = run_cli_raw(["status"])
        assert exit_code == 0
        assert "kdeconnect-cli 26.08.1" in stdout

    def test_status_kdeconnect_missing(self):
        exit_code, stdout, stderr = run_cli_raw(["status"], bridge=MissingBinaryBridge())
        assert exit_code == 1
        assert "Error: KDE Connect CLI 'kdeconnect' was not found." in stderr

    def test_status_command_failure(self):
        exit_code, stdout, stderr = run_cli_raw(["status"], bridge=FailingBridge("Command failed"))
        assert exit_code == 1
        assert "Error: Command failed" in stderr


class TestDevicesCommand:
    """Test 'devices' command."""

    def test_devices_success(self):
        exit_code, stdout, stderr = run_cli_raw(["devices"])
        assert exit_code == 0
        assert "POCO C71" in stdout
        assert "8599f9fc623f4dcbb097f80488529359" in stdout

    def test_devices_kdeconnect_missing(self):
        exit_code, stdout, stderr = run_cli_raw(["devices"], bridge=MissingBinaryBridge())
        assert exit_code == 1
        assert "Error: KDE Connect CLI 'kdeconnect' was not found." in stderr

    def test_devices_command_failure(self):
        exit_code, stdout, stderr = run_cli_raw(["devices"], bridge=FailingBridge("List failed"))
        assert exit_code == 1
        assert "Error: List failed" in stderr


class TestAvailableCommand:
    """Test 'available' command."""

    def test_available_success(self):
        exit_code, stdout, stderr = run_cli_raw(["available"])
        assert exit_code == 0
        assert "POCO C71" in stdout

    def test_available_kdeconnect_missing(self):
        exit_code, stdout, stderr = run_cli_raw(["available"], bridge=MissingBinaryBridge())
        assert exit_code == 1
        assert "Error: KDE Connect CLI 'kdeconnect' was not found." in stderr

    def test_available_command_failure(self):
        exit_code, stdout, stderr = run_cli_raw(["available"], bridge=FailingBridge("List failed"))
        assert exit_code == 1
        assert "Error: List failed" in stderr


class TestRefreshCommand:
    """Test 'refresh' command."""

    def test_refresh_success(self):
        exit_code, stdout, stderr = run_cli_raw(["refresh"])
        assert exit_code == 0
        assert "Refreshed" in stdout

    def test_refresh_kdeconnect_missing(self):
        exit_code, stdout, stderr = run_cli_raw(["refresh"], bridge=MissingBinaryBridge())
        assert exit_code == 1
        assert "Error: KDE Connect CLI 'kdeconnect' was not found." in stderr

    def test_refresh_command_failure(self):
        exit_code, stdout, stderr = run_cli_raw(["refresh"], bridge=FailingBridge("Refresh failed"))
        assert exit_code == 1
        assert "Error: Refresh failed" in stderr


class TestEncryptionCommand:
    """Test 'encryption' command."""

    def test_encryption_with_device_success(self):
        exit_code, stdout, stderr = run_cli_raw(["encryption", "--device", "8599f9fc623f4dcbb097f80488529359"])
        assert exit_code == 0
        assert "SHA256 fingerprint" in stdout
        assert "Protocol version: 8" in stdout

    def test_encryption_without_device_fails(self):
        exit_code, stdout, stderr = run_cli_raw(["encryption"])
        assert exit_code == 1
        assert "Error: No device specified" in stderr

    def test_encryption_kdeconnect_missing(self):
        exit_code, stdout, stderr = run_cli_raw(
            ["encryption", "--device", "8599f9fc623f4dcbb097f80488529359"],
            bridge=MissingBinaryBridge()
        )
        assert exit_code == 1
        assert "Error: KDE Connect CLI 'kdeconnect' was not found." in stderr

    def test_encryption_command_failure(self):
        exit_code, stdout, stderr = run_cli_raw(
            ["encryption", "--device", "8599f9fc623f4dcbb097f80488529359"],
            bridge=FailingBridge("Encryption failed")
        )
        assert exit_code == 1
        assert "Error: Encryption failed" in stderr


class TestPingCommand:
    """Test 'ping' command."""

    def test_ping_with_device_success(self):
        exit_code, stdout, stderr = run_cli_raw(["ping", "--device", "8599f9fc623f4dcbb097f80488529359"])
        assert exit_code == 0
        assert stdout.strip() == ""

    def test_ping_without_device_fails(self):
        exit_code, stdout, stderr = run_cli_raw(["ping"])
        assert exit_code == 1
        assert "Error: No device specified" in stderr

    def test_ping_kdeconnect_missing(self):
        exit_code, stdout, stderr = run_cli_raw(
            ["ping", "--device", "8599f9fc623f4dcbb097f80488529359"],
            bridge=MissingBinaryBridge()
        )
        assert exit_code == 1
        assert "Error: KDE Connect CLI 'kdeconnect' was not found." in stderr

    def test_ping_command_failure(self):
        exit_code, stdout, stderr = run_cli_raw(
            ["ping", "--device", "8599f9fc623f4dcbb097f80488529359"],
            bridge=FailingBridge("Ping failed")
        )
        assert exit_code == 1
        assert "Error: Ping failed" in stderr


class TestShareCommand:
    """Test 'share' command."""

    def test_share_with_device_success(self):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.is_file", return_value=True):
                with patch("pathlib.Path.expanduser", return_value=Path("/tmp/test.txt")):
                    with patch("pathlib.Path.resolve", return_value=Path("/tmp/test.txt")):
                        exit_code, stdout, stderr = run_cli_raw(["share", "/tmp/test.txt", "--device", "8599f9fc623f4dcbb097f80488529359"])
        assert exit_code == 0
        assert "Shared file:///tmp/test.txt" in stdout

    def test_share_without_device_fails(self):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.is_file", return_value=True):
                with patch("pathlib.Path.expanduser", return_value=Path("/tmp/test.txt")):
                    with patch("pathlib.Path.resolve", return_value=Path("/tmp/test.txt")):
                        exit_code, stdout, stderr = run_cli_raw(["share", "/tmp/test.txt"])
        assert exit_code == 1
        assert "Error: No device specified" in stderr

    def test_share_nonexistent_file_fails(self):
        with patch("pathlib.Path.exists", return_value=False):
            with patch("pathlib.Path.expanduser", return_value=Path("/nonexistent.txt")):
                with patch("pathlib.Path.resolve", return_value=Path("/nonexistent.txt")):
                    exit_code, stdout, stderr = run_cli_raw(["share", "/nonexistent.txt", "--device", "8599f9fc623f4dcbb097f80488529359"])
        assert exit_code == 1
        assert "Error: File not found" in stderr

    def test_share_directory_fails(self):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.is_file", return_value=False):
                with patch("pathlib.Path.expanduser", return_value=Path("/tmp")):
                    with patch("pathlib.Path.resolve", return_value=Path("/tmp")):
                        exit_code, stdout, stderr = run_cli_raw(["share", "/tmp", "--device", "8599f9fc623f4dcbb097f80488529359"])
        assert exit_code == 1
        assert "Error: Path is not a file" in stderr

    def test_share_kdeconnect_missing(self):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.is_file", return_value=True):
                with patch("pathlib.Path.expanduser", return_value=Path("/tmp/test.txt")):
                    with patch("pathlib.Path.resolve", return_value=Path("/tmp/test.txt")):
                        exit_code, stdout, stderr = run_cli_raw(
                            ["share", "/tmp/test.txt", "--device", "8599f9fc623f4dcbb097f80488529359"],
                            bridge=MissingBinaryBridge()
                        )
        assert exit_code == 1
        assert "Error: KDE Connect CLI 'kdeconnect' was not found." in stderr

    def test_share_command_failure(self):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.is_file", return_value=True):
                with patch("pathlib.Path.expanduser", return_value=Path("/tmp/test.txt")):
                    with patch("pathlib.Path.resolve", return_value=Path("/tmp/test.txt")):
                        exit_code, stdout, stderr = run_cli_raw(
                            ["share", "/tmp/test.txt", "--device", "8599f9fc623f4dcbb097f80488529359"],
                            bridge=FailingBridge("Share failed")
                        )
        assert exit_code == 1
        assert "Error: Share failed" in stderr


class TestShareTextCommand:
    """Test 'share-text' command."""

    def test_share_text_with_device_success(self):
        exit_code, stdout, stderr = run_cli_raw(["share-text", "hello world", "--device", "8599f9fc623f4dcbb097f80488529359"])
        assert exit_code == 0
        assert "Shared text: hello world" in stdout

    def test_share_text_without_device_fails(self):
        exit_code, stdout, stderr = run_cli_raw(["share-text", "hello world"])
        assert exit_code == 1
        assert "Error: No device specified" in stderr

    def test_share_text_kdeconnect_missing(self):
        exit_code, stdout, stderr = run_cli_raw(
            ["share-text", "hello world", "--device", "8599f9fc623f4dcbb097f80488529359"],
            bridge=MissingBinaryBridge()
        )
        assert exit_code == 1
        assert "Error: KDE Connect CLI 'kdeconnect' was not found." in stderr

    def test_share_text_command_failure(self):
        exit_code, stdout, stderr = run_cli_raw(
            ["share-text", "hello world", "--device", "8599f9fc623f4dcbb097f80488529359"],
            bridge=FailingBridge("Share text failed")
        )
        assert exit_code == 1
        assert "Error: Share text failed" in stderr


class TestCLIArguments:
    """Test CLI argument parsing edge cases."""

    def test_missing_command_shows_help(self):
        with patch("sys.argv", ["fox-phone"]):
            with patch("sys.stderr", new=MagicMock()) as mock_stderr:
                try:
                    main()
                    exit_code = 0
                except SystemExit as e:
                    exit_code = e.code
                assert exit_code != 0

    def test_invalid_command_shows_error(self):
        with patch("sys.argv", ["fox-phone", "invalid-command"]):
            with patch("sys.stderr", new=MagicMock()) as mock_stderr:
                try:
                    main()
                    exit_code = 0
                except SystemExit as e:
                    exit_code = e.code
                assert exit_code != 0

    def test_help_flag(self):
        with patch("sys.argv", ["fox-phone", "--help"]):
            with patch("sys.stdout", new=MagicMock()) as mock_stdout:
                with patch("sys.stderr", new=MagicMock()) as mock_stderr:
                    try:
                        main()
                        exit_code = 0
                    except SystemExit as e:
                        exit_code = e.code
                assert exit_code == 0


class TestBridgeUnit:
    """Unit tests for KDEConnectBridge (mocking subprocess)."""

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_version_calls_subprocess(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="kdeconnect-cli 26.08.1\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.version()
        assert result == "kdeconnect-cli 26.08.1"
        mock_run.assert_called_once_with(["kdeconnect-cli", "--version"], capture_output=True, text=True, check=True)

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_list_devices_calls_subprocess(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="device1\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.list_devices()
        assert result == "device1"
        mock_run.assert_called_once_with(["kdeconnect-cli", "--list-devices"], capture_output=True, text=True, check=True)

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_list_available_calls_subprocess(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="device1\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.list_available()
        assert result == "device1"
        mock_run.assert_called_once_with(["kdeconnect-cli", "--list-available"], capture_output=True, text=True, check=True)

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_refresh_calls_subprocess(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="OK\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.refresh()
        assert result == "OK"
        mock_run.assert_called_once_with(["kdeconnect-cli", "--refresh"], capture_output=True, text=True, check=True)

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_encryption_info_with_device(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="info\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.encryption_info("device123")
        assert result == "info"
        mock_run.assert_called_once_with(["kdeconnect-cli", "--encryption-info", "--device", "device123"], capture_output=True, text=True, check=True)

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_encryption_info_without_device(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="info\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.encryption_info()
        assert result == "info"
        mock_run.assert_called_once_with(["kdeconnect-cli", "--encryption-info"], capture_output=True, text=True, check=True)

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_ping_with_device(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="pong\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.ping("device123")
        assert result == "pong"
        mock_run.assert_called_once_with(["kdeconnect-cli", "--ping", "--device", "device123"], capture_output=True, text=True, check=True)

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_ping_without_device(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="pong\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.ping()
        assert result == "pong"
        mock_run.assert_called_once_with(["kdeconnect-cli", "--ping"], capture_output=True, text=True, check=True)

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_share_with_device(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="shared\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.share("/path/file.txt", "device123")
        assert result == "shared"
        mock_run.assert_called_once_with(["kdeconnect-cli", "--share", "/path/file.txt", "--device", "device123"], capture_output=True, text=True, check=True)

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_share_without_device(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="shared\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.share("/path/file.txt")
        assert result == "shared"
        mock_run.assert_called_once_with(["kdeconnect-cli", "--share", "/path/file.txt"], capture_output=True, text=True, check=True)

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_share_text_with_device(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="shared\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.share_text("hello", "device123")
        assert result == "shared"
        mock_run.assert_called_once_with(["kdeconnect-cli", "--share-text", "hello", "--device", "device123"], capture_output=True, text=True, check=True)

    @patch("shutil.which", return_value=None)
    @patch("os.path.isfile", return_value=False)
    @patch("os.access", return_value=False)
    def test_missing_binary_raises_error(self, mock_access, mock_isfile, mock_which):
        bridge = KDEConnectBridge()
        with pytest.raises(KDEConnectError, match="KDE Connect CLI 'kdeconnect-cli' was not found"):
            bridge.version()

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_subprocess_error_raises_kdeconnect_error(self, mock_run, mock_isfile, mock_which):
        mock_run.side_effect = subprocess.CalledProcessError(1, "kdeconnect-cli", stderr="error output")
        bridge = KDEConnectBridge()
        with pytest.raises(KDEConnectError, match="error output"):
            bridge.version()

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_subprocess_error_with_empty_stderr(self, mock_run, mock_isfile, mock_which):
        exc = subprocess.CalledProcessError(1, "kdeconnect-cli", output="stdout output", stderr="")
        mock_run.side_effect = exc
        bridge = KDEConnectBridge()
        with pytest.raises(KDEConnectError, match="stdout output"):
            bridge.version()


import subprocess  # needed for subprocess.CalledProcessError in tests above