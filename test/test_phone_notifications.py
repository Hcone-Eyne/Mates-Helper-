"""Additional tests for phone notification and SMS functionality."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from phone.bridge.kdeconnect import KDEConnectBridge, KDEConnectError
from phone.phone_cli.phone_cli import main
from phone.security.permission import (
    DEFAULT_PERMISSIONS,
    PhonePermision,
)

# Reuse mock classes from test_phone_cli.py
from test.test_phone_cli import (
    MockBridge,
    FailingBridge,
    MissingBinaryBridge,
    run_cli_raw,
)


def run_cli_with_policy(args, bridge=None, permissions=None):
    """Run the CLI with an explicit permission policy.

    The shared ``run_cli_raw`` helper always uses the default policy, so
    notification and SMS success paths need this test-local variant to inject
    the explicit grants required by least privilege.
    """
    if bridge is None:
        bridge = MockBridge()

    with patch("phone.phone_cli.phone_cli.KDEConnectBridge") as bridge_cls:
        bridge_cls.return_value = bridge
        with patch("sys.stdout", new=MagicMock()) as mock_stdout:
            with patch("sys.stderr", new=MagicMock()) as mock_stderr:
                try:
                    main(args, permissions=permissions)
                    exit_code = 0
                except SystemExit as e:
                    exit_code = e.code
                stdout_calls = [str(c[0][0]) for c in mock_stdout.write.call_args_list] if mock_stdout.write.called else []
                stderr_calls = [str(c[0][0]) for c in mock_stderr.write.call_args_list] if mock_stderr.write.called else []
                return exit_code, "".join(stdout_calls), "".join(stderr_calls), bridge_cls


def notifications_policy():
    policy = dict(DEFAULT_PERMISSIONS)
    policy[PhonePermision.NOTIFICATIONS] = True
    return policy


def send_message_policy():
    policy = dict(DEFAULT_PERMISSIONS)
    policy[PhonePermision.SEND_MESSAGE] = True
    return policy


class TestNotificationsCommand:
    """Test 'notifications' command."""

    def test_notifications_with_device_success(self):
        bridge = MockBridge()
        bridge.get_notifications = lambda device: [
            {
                "id": "123",
                "appName": "TestApp",
                "title": "Test Title",
                "text": "Test body",
            }
        ]
        exit_code, stdout, stderr, bridge_cls = run_cli_with_policy(
            ["notifications", "--device", "8599f9fc623f4dcbb097f80488529359"],
            bridge=bridge,
            permissions=notifications_policy(),
        )
        assert exit_code == 0
        bridge_cls.assert_called_once_with()
        assert "TestApp" in stdout
        assert "Test Title" in stdout
        assert "Test body" in stdout

    def test_notifications_json_output(self):
        bridge = MockBridge()
        bridge.get_notifications = lambda device: [
            {"id": "123", "appName": "TestApp", "title": "Test", "text": "Body"}
        ]
        exit_code, stdout, stderr, bridge_cls = run_cli_with_policy(
            ["notifications", "--device", "8599f9fc623f4dcbb097f80488529359", "--json"],
            bridge=bridge,
            permissions=notifications_policy(),
        )
        assert exit_code == 0
        bridge_cls.assert_called_once_with()
        data = json.loads(stdout)
        assert isinstance(data, list)
        assert data[0]["appName"] == "TestApp"

    def test_notifications_empty(self):
        bridge = MockBridge()
        bridge.get_notifications = lambda device: []
        exit_code, stdout, stderr, bridge_cls = run_cli_with_policy(
            ["notifications", "--device", "8599f9fc623f4dcbb097f80488529359"],
            bridge=bridge,
            permissions=notifications_policy(),
        )
        assert exit_code == 0
        bridge_cls.assert_called_once_with()
        assert "No notifications found" in stdout

    def test_notifications_denied_by_default_before_bridge(self):
        exit_code, stdout, stderr, bridge_cls = run_cli_with_policy(
            ["notifications", "--device", "8599f9fc623f4dcbb097f80488529359"],
            bridge=MockBridge(),
            permissions=None,
        )
        assert exit_code == 1
        bridge_cls.assert_not_called()
        assert "Permission denied" in stderr
        assert "Notifications" in stderr


class TestSmsCommand:
    """Test 'sms' command."""

    def test_sms_with_device_success(self):
        bridge = MockBridge()
        bridge.send_sms = lambda dest, msg, device: "SMS sent"
        exit_code, stdout, stderr, bridge_cls = run_cli_with_policy(
            ["sms", "--device", "8599f9fc623f4dcbb097f80488529359", "+1234567890", "Hello"],
            bridge=bridge,
            permissions=send_message_policy(),
        )
        assert exit_code == 0
        bridge_cls.assert_called_once_with()
        assert "SMS sent" in stdout

    def test_sms_denied_by_default_before_bridge(self):
        exit_code, stdout, stderr, bridge_cls = run_cli_with_policy(
            ["sms", "--device", "8599f9fc623f4dcbb097f80488529359", "+1234567890", "Hello"],
            bridge=MockBridge(),
            permissions=None,
        )
        assert exit_code == 1
        bridge_cls.assert_not_called()
        assert "Permission denied" in stderr
        assert "Send Message" in stderr

    def test_sms_without_destination_fails(self):
        exit_code, stdout, stderr = run_cli_raw(["sms"])
        # argparse exits with code 2 for missing required arguments
        assert exit_code == 2
        assert "the following arguments are required: destination, message" in stderr

    def test_sms_without_message_fails(self):
        exit_code, stdout, stderr = run_cli_raw(
            ["sms", "--device", "8599f9fc623f4dcbb097f80488529359", "+1234567890"]
        )
        # argparse exits with code 2 for missing required arguments
        assert exit_code == 2
        assert "the following arguments are required: message" in stderr

    def test_sms_kdeconnect_missing(self):
        exit_code, stdout, stderr, bridge_cls = run_cli_with_policy(
            ["sms", "--device", "8599f9fc623f4dcbb097f80488529359", "+1234567890", "test"],
            bridge=MissingBinaryBridge(),
            permissions=send_message_policy(),
        )
        assert exit_code == 1
        bridge_cls.assert_called_once_with()
        assert "Error: KDE Connect CLI 'kdeconnect' was not found." in stderr


class TestBridgeUnitExtended:
    """Additional unit tests for KDEConnectBridge new methods."""

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_list_notifications_calls_subprocess(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="[]\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.list_notifications("device123")
        assert result == "[]"
        mock_run.assert_called_once_with(
            ["kdeconnect-cli", "--list-notifications", "--device", "device123"],
            capture_output=True, text=True, check=True, timeout=30
        )

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_list_notifications_without_device(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="[]\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.list_notifications()
        assert result == "[]"
        mock_run.assert_called_once_with(
            ["kdeconnect-cli", "--list-notifications"],
            capture_output=True, text=True, check=True, timeout=30
        )

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_send_sms_with_device(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="sent\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.send_sms("+1234567890", "Hello", "device123")
        assert result == "sent"
        mock_run.assert_called_once_with(
            ["kdeconnect-cli", "--send-sms", "Hello", "--destination", "+1234567890", "--device", "device123"],
            capture_output=True, text=True, check=True, timeout=30
        )

    @patch("shutil.which", return_value="/usr/bin/kdeconnect-cli")
    @patch("os.path.isfile", return_value=False)
    @patch("subprocess.run")
    def test_send_sms_without_device(self, mock_run, mock_isfile, mock_which):
        mock_run.return_value = MagicMock(stdout="sent\n", stderr="", returncode=0)
        bridge = KDEConnectBridge()
        result = bridge.send_sms("+1234567890", "Hello")
        assert result == "sent"
        mock_run.assert_called_once_with(
            ["kdeconnect-cli", "--send-sms", "Hello", "--destination", "+1234567890"],
            capture_output=True, text=True, check=True, timeout=30
        )