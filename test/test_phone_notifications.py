"""Additional tests for phone notification and SMS functionality."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from phone.bridge.kdeconnect import KDEConnectBridge, KDEConnectError
from phone.phone_cli.phone_cli import main

# Reuse mock classes from test_phone_cli.py
from test.test_phone_cli import (
    MockBridge,
    FailingBridge,
    MissingBinaryBridge,
    run_cli_raw,
)


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
        exit_code, stdout, stderr = run_cli_raw(
            ["notifications", "--device", "8599f9fc623f4dcbb097f80488529359"],
            bridge=bridge,
        )
        assert exit_code == 0
        assert "TestApp" in stdout
        assert "Test Title" in stdout
        assert "Test body" in stdout

    def test_notifications_json_output(self):
        bridge = MockBridge()
        bridge.get_notifications = lambda device: [
            {"id": "123", "appName": "TestApp", "title": "Test", "text": "Body"}
        ]
        exit_code, stdout, stderr = run_cli_raw(
            ["notifications", "--device", "8599f9fc623f4dcbb097f80488529359", "--json"],
            bridge=bridge,
        )
        assert exit_code == 0
        data = json.loads(stdout)
        assert isinstance(data, list)
        assert data[0]["appName"] == "TestApp"

    def test_notifications_empty(self):
        bridge = MockBridge()
        bridge.get_notifications = lambda device: []
        exit_code, stdout, stderr = run_cli_raw(
            ["notifications", "--device", "8599f9fc623f4dcbb097f80488529359"],
            bridge=bridge,
        )
        assert exit_code == 0
        assert "No notifications found" in stdout


class TestSmsCommand:
    """Test 'sms' command."""

    def test_sms_with_device_success(self):
        bridge = MockBridge()
        bridge.send_sms = lambda dest, msg, device: "SMS sent"
        exit_code, stdout, stderr = run_cli_raw(
            ["sms", "--device", "8599f9fc623f4dcbb097f80488529359", "+1234567890", "Hello"],
            bridge=bridge,
        )
        assert exit_code == 0
        assert "SMS sent" in stdout

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
        exit_code, stdout, stderr = run_cli_raw(
            ["sms", "--device", "8599f9fc623f4dcbb097f80488529359", "+1234567890", "test"],
            bridge=MissingBinaryBridge(),
        )
        assert exit_code == 1
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
            capture_output=True, text=True, check=True
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
            capture_output=True, text=True, check=True
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
            capture_output=True, text=True, check=True
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
            capture_output=True, text=True, check=True
        )