"""Enforcement tests for the Phone Hub's two security controls.

These tests prove the controls actually gate behaviour at runtime:

1. Isolation - agent-side callers (Fox / Fox Club / Ollama / members) are
   refused by `assert_phone_boundary`, called from the CLI entry point and
   from the bridge itself, not only from the test suite.
2. Permissions - `require_permission` refuses a command whose permission is
   not granted *before* the bridge is created, so a denied operation can
   never reach the device.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from phone.bridge.kdeconnect import (
    KDEConnectBridge,
    KDEConnectUnsupportedError,
)
from phone.phone_cli import phone_cli
from phone.security.isolation import PhoneIsolationError, assert_phone_boundary
from phone.security.permission import (
    COMMAND_PERMISSIONS,
    DEFAULT_PERMISSIONS,
    PhonePermision,
    PhonePermissionDenied,
    command_permission,
    is_allowed,
    require_permission,
)


REPO_ROOT = Path(__file__).resolve().parent.parent

ALLOWED_SOURCES = ["phone_cli", "system", "user", "kdeconnect", "", "   "]
AGENT_SOURCES = [
    "fox",
    "FOX",
    "Fox_Agent",
    "  fox  ",
    "fox club",
    "fox-club",
    "fox_club_tools",
    "agent",
    "agent/ollama",
    "ollama",
    "Ollama-Agent",
    "julie",
    "annie",
    "selina",
    "gwen",
]


class TestIsolationBoundary:

    @pytest.mark.parametrize("source", ALLOWED_SOURCES)
    def test_trusted_sources_are_allowed(self, source):
        assert assert_phone_boundary(source) is None

    @pytest.mark.parametrize("source", AGENT_SOURCES)
    def test_agent_sources_are_refused(self, source):
        with pytest.raises(PhoneIsolationError, match="isolated"):
            assert_phone_boundary(source)

    def test_boundary_error_is_a_permission_error(self):
        with pytest.raises(PermissionError):
            assert_phone_boundary("fox")

    def test_cli_refuses_agent_source(self, capsys):
        with pytest.raises(SystemExit) as exc:
            phone_cli.main(["status"], source="fox")
        assert exc.value.code == 1
        assert "isolated" in capsys.readouterr().err

    def test_cli_agent_source_never_builds_a_bridge(self):
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge") as bridge_cls:
            with pytest.raises(SystemExit):
                phone_cli.main(["status"], source="ollama")
        bridge_cls.assert_not_called()

    @pytest.mark.parametrize("command", [["sms", "15551234567", "hi"], ["notifications"], ["share-text", "hi"]])
    def test_agent_cannot_reach_any_device_command(self, command, capsys):
        with pytest.raises(SystemExit) as exc:
            phone_cli.main(command, source="fox_club")
        assert exc.value.code == 1
        assert "isolated" in capsys.readouterr().err

    def test_bridge_construction_refuses_agent_source(self):
        with pytest.raises(PhoneIsolationError):
            KDEConnectBridge(source="ollama")

    def test_bridge_refuses_agent_source_on_every_call(self):
        # Construction with a trusted source, then the source is swapped to an
        # agent identity: the per-call check must still refuse.
        bridge = KDEConnectBridge(source="phone_cli")
        bridge.source = "fox_agent"
        with pytest.raises(PhoneIsolationError):
            bridge._run("--version")

    def test_bridge_with_trusted_source_still_runs(self):
        with patch("shutil.which", return_value="/usr/bin/kdeconnect-cli"), \
                patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
            assert KDEConnectBridge(source="phone_cli")._run("--version") == "ok"


class TestPermissionEnforcement:

    def test_require_permission_allows_granted_permission(self):
        assert require_permission(PhonePermision.Status) is True
        assert require_permission(PhonePermision.FILES) is True

    def test_require_permission_denies_withheld_permission(self):
        with pytest.raises(PhonePermissionDenied, match="Make Call"):
            require_permission(PhonePermision.MAKE_CALL)

    def test_require_permission_reads_injected_policy(self):
        policy = dict(DEFAULT_PERMISSIONS)
        policy[PhonePermision.NOTIFICATIONS] = True

        assert require_permission(PhonePermision.NOTIFICATIONS, policy) is True

        # ...and the same permission is withheld under the default policy
        with pytest.raises(PhonePermissionDenied, match="Notifications"):
            require_permission(PhonePermision.NOTIFICATIONS)

    def test_every_mapped_command_is_gated(self):
        assert COMMAND_PERMISSIONS
        for command in COMMAND_PERMISSIONS:
            assert command_permission(command) is not None

    def test_unknown_command_is_not_gated(self):
        assert command_permission("not-a-command") is None
        assert command_permission(None) is None

    def test_default_policy_keeps_discovery_and_files_usable(self):
        # The hub stays usable out of the box for diagnostics and file
        # sharing - the commands that carry no private device data.
        for command, permission in COMMAND_PERMISSIONS.items():
            if permission in {PhonePermision.Status, PhonePermision.FILES}:
                assert is_allowed(permission, DEFAULT_PERMISSIONS), (
                    f"default policy blocks '{command}'"
                )

    def test_privacy_commands_are_withheld_until_granted(self):
        # Private device data (notifications, messages), outgoing actions
        # (send message) and calls are least privilege: denied unless a
        # policy grants them explicitly.
        for permission in (
            PhonePermision.NOTIFICATIONS,
            PhonePermision.MESSAGES,
            PhonePermision.SEND_MESSAGE,
            PhonePermision.CALLS,
            PhonePermision.MAKE_CALL,
        ):
            assert is_allowed(permission, DEFAULT_PERMISSIONS) is False, (
                f"{permission} must not be granted by default"
            )

    def test_calls_stay_withheld_by_default(self):
        assert is_allowed(PhonePermision.CALLS, DEFAULT_PERMISSIONS) is False
        assert is_allowed(PhonePermision.MAKE_CALL, DEFAULT_PERMISSIONS) is False

    def test_denied_notifications_never_reaches_the_bridge(self):
        policy = dict(DEFAULT_PERMISSIONS)
        policy[PhonePermision.NOTIFICATIONS] = False

        with patch("phone.phone_cli.phone_cli.KDEConnectBridge") as bridge_cls:
            with pytest.raises(SystemExit) as exc:
                phone_cli.main(["notifications"], permissions=policy)

        assert exc.value.code == 1
        bridge_cls.assert_not_called()

    def test_denied_sms_send_never_reaches_the_bridge(self):
        policy = dict(DEFAULT_PERMISSIONS)
        policy[PhonePermision.SEND_MESSAGE] = False

        with patch("phone.phone_cli.phone_cli.KDEConnectBridge") as bridge_cls:
            with pytest.raises(SystemExit) as exc:
                phone_cli.main(["sms", "15551234567", "hello"], permissions=policy)

        assert exc.value.code == 1
        bridge_cls.assert_not_called()

    def test_denied_permission_message_is_reported(self, capsys):
        policy = {permission: False for permission in PhonePermision}

        with pytest.raises(SystemExit):
            phone_cli.main(["devices"], permissions=policy)

        assert "Permission denied" in capsys.readouterr().err

    def test_granted_policy_builds_the_bridge(self):
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge") as bridge_cls:
            bridge_cls.return_value = MagicMock(version=lambda: "26.08.1")
            phone_cli.main(["status"])
        bridge_cls.assert_called_once_with()

    def test_permissions_screen_declares_local_policy(self, capsys):
        phone_cli.show_permission("some-device")
        out = capsys.readouterr().out
        assert "local policy" in out
        assert "not a readback from the device" in out

    def test_permissions_screen_can_show_a_restricted_policy(self, capsys):
        policy = dict(DEFAULT_PERMISSIONS)
        policy[PhonePermision.SEND_MESSAGE] = False

        phone_cli.show_permission(None, policy)
        out = capsys.readouterr().out
        assert "Send Message" in out
        assert "○" in out


class TestNoPhoneExposureToAgents:

    REGISTRIES = [
        REPO_ROOT / "agent" / "ollama" / "tools.py",
        REPO_ROOT / "brain" / "tools.py",
        REPO_ROOT / "mcp_plugins" / "mcp_server.py",
    ]

    @pytest.mark.parametrize("path", REGISTRIES)
    def test_tool_registry_does_not_import_phone(self, path):
        source = path.read_text()
        assert "phone." not in source, f"{path} exposes phone modules"
        assert "phone_cli" not in source, f"{path} exposes the phone CLI"

    def test_only_the_phone_package_asserts_the_boundary(self):
        offenders = []
        for path in REPO_ROOT.rglob("*.py"):
            if "venv" in path.parts or "phone" in path.parts or "test" in path.parts:
                continue
            if "assert_phone_boundary" in path.read_text(errors="ignore"):
                offenders.append(str(path.relative_to(REPO_ROOT)))
        assert offenders == []


class TestUntrustedSourcesAndAgentCallers:
    """The boundary used to be a denylist of agent names.

    Anything else was trusted by default, so an unaudited source label or a
    call made from inside an agent module slipped straight through.
    """

    UNTRUSTED = ["not_a_known_source", "random_tool", "CLI_TOOL", "chatgpt", "phone"]

    @pytest.mark.parametrize("source", UNTRUSTED)
    def test_untrusted_source_is_refused(self, source):
        with pytest.raises(PhoneIsolationError, match="isolated"):
            assert_phone_boundary(source)

    def test_refusal_names_the_rejected_source(self):
        with pytest.raises(PhoneIsolationError, match="not an allowlisted"):
            assert_phone_boundary("not_a_known_source")

    @pytest.mark.parametrize("source", ALLOWED_SOURCES)
    def test_allowlisted_sources_still_pass(self, source):
        assert assert_phone_boundary(source) is None

    @pytest.mark.parametrize("source", AGENT_SOURCES)
    def test_agent_labels_are_still_refused(self, source):
        with pytest.raises(PhoneIsolationError, match="isolated"):
            assert_phone_boundary(source)

    def test_cli_exits_before_building_a_bridge_for_an_untrusted_source(self, capsys):
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge") as bridge:
            with pytest.raises(SystemExit) as exc:
                phone_cli.main(["status"], source="not_a_known_source")

        assert exc.value.code == 1
        assert "isolated" in capsys.readouterr().err
        bridge.assert_not_called()

    def test_agent_module_cannot_label_itself_phone_cli(self):
        # The source label is attacker-controlled; the call stack is not.
        sneaky = REPO_ROOT / "agent" / "ollama" / "sneaky_caller.py"
        code = compile(
            "from phone.security.isolation import assert_phone_boundary\n"
            "assert_phone_boundary('phone_cli')\n",
            str(sneaky),
            "exec",
        )

        with pytest.raises(PhoneIsolationError, match="isolated"):
            exec(code, {})

    def test_agent_module_refusal_reports_where_it_came_from(self):
        sneaky = REPO_ROOT / "brain" / "tools.py"
        code = compile(
            "from phone.security.isolation import assert_phone_boundary\n"
            "assert_phone_boundary('system')\n",
            str(sneaky),
            "exec",
        )

        with pytest.raises(PhoneIsolationError, match="agent-side module"):
            exec(code, {})

    def test_a_non_agent_caller_with_a_trusted_source_is_allowed(self):
        script = REPO_ROOT / "user_script.py"
        code = compile(
            "from phone.security.isolation import assert_phone_boundary\n"
            "assert_phone_boundary('phone_cli')\n",
            str(script),
            "exec",
        )

        assert exec(code, {}) is None


# ---------------------------------------------------------------------------
# Full gating matrix: every command that requires a permission is refused
# before the bridge exists when its own permission is withheld.
# ---------------------------------------------------------------------------

COMMAND_ARGV = {
    "status": ["status"],
    "devices": ["devices"],
    "available": ["available"],
    "refresh": ["refresh"],
    "encryption": ["encryption"],
    "ping": ["ping"],
    "permissions": ["permissions"],
    "share": ["share", "/tmp/phone-hub-gate.txt"],
    "share-text": ["share-text", "hello"],
    "notifications": ["notifications"],
    "messages": ["messages"],
    "list-sms": ["list-sms"],
    "sms": ["sms", "15551234567", "hello"],
}


class TestEveryCommandIsGated:

    @pytest.mark.parametrize("command", sorted(COMMAND_PERMISSIONS))
    def test_withheld_permission_blocks_the_command_before_the_bridge(self, command):
        policy = dict(DEFAULT_PERMISSIONS)
        policy[command_permission(command)] = False

        with patch("phone.phone_cli.phone_cli.KDEConnectBridge") as bridge_cls:
            with pytest.raises(SystemExit) as exc:
                phone_cli.main(COMMAND_ARGV[command], permissions=policy)

        assert exc.value.code == 1
        bridge_cls.assert_not_called()

    def test_every_cli_command_has_a_permission(self):
        # No subcommand may be added to the CLI without declaring the
        # permission it needs - an ungated command would reach the device.
        parser_argv = COMMAND_ARGV.keys()
        assert set(COMMAND_PERMISSIONS) == set(parser_argv), (
            "commands missing a permission mapping: "
            f"{set(parser_argv) ^ set(COMMAND_PERMISSIONS)}"
        )

    def test_empty_policy_denies_everything(self):
        # An explicitly empty policy is a real deny-all - it must never be
        # silently swapped for the default policy.
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge") as bridge_cls:
            with pytest.raises(SystemExit) as exc:
                phone_cli.main(["status"], permissions={})

        assert exc.value.code == 1
        bridge_cls.assert_not_called()

    @pytest.mark.parametrize(
        "command",
        ["notifications", "messages", "list-sms", "sms"],
    )
    def test_privacy_commands_are_denied_by_default(self, command, capsys):
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge") as bridge_cls:
            with pytest.raises(SystemExit) as exc:
                phone_cli.main(COMMAND_ARGV[command])

        assert exc.value.code == 1
        bridge_cls.assert_not_called()
        assert "Permission denied" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "command,method,reply",
        [
            ("status", "version", "26.08.1"),
            ("devices", "list_devices", "1 device found"),
            ("available", "list_available", "1 device found"),
            ("refresh", "refresh", "Refreshed"),
        ],
    )
    def test_discovery_commands_stay_usable_by_default(
        self, command, method, reply, capsys
    ):
        bridge = MagicMock()
        getattr(bridge, method).return_value = reply
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge", return_value=bridge):
            phone_cli.main([command])
        getattr(bridge, method).assert_called_once_with()
        assert reply in capsys.readouterr().out


class TestExplicitGrants:
    """Withheld permissions are a default, not a hard ban."""

    def test_explicit_grant_re_enables_notifications(self):
        policy = dict(DEFAULT_PERMISSIONS)
        policy[PhonePermision.NOTIFICATIONS] = True
        bridge = MagicMock()
        bridge.get_notifications.return_value = [
            {"id": "1", "appName": "TestApp", "title": "Test", "text": "Body"}
        ]

        with patch("phone.phone_cli.phone_cli.KDEConnectBridge", return_value=bridge):
            phone_cli.main(["notifications"], permissions=policy)

        bridge.get_notifications.assert_called_once_with(None)

    def test_explicit_grant_re_enables_send_message(self):
        policy = dict(DEFAULT_PERMISSIONS)
        policy[PhonePermision.SEND_MESSAGE] = True
        bridge = MagicMock()
        bridge.send_sms.return_value = "SMS sent"

        with patch("phone.phone_cli.phone_cli.KDEConnectBridge", return_value=bridge):
            phone_cli.main(
                ["sms", "15551234567", "hello"], permissions=policy
            )

        bridge.send_sms.assert_called_once_with("15551234567", "hello", None)


class TestBridgeRefusesSwappedSourcesEverywhere:
    """The per-call check covers every method that can touch the device."""

    DEVICE_CALLS = [
        ("version", ()),
        ("list_devices", ()),
        ("list_available", ()),
        ("refresh", ()),
        ("encryption_info", ()),
        ("ping", ()),
        ("share", ("/tmp/x",)),
        ("share_text", ("hello",)),
        ("list_notifications", ()),
        ("send_sms", ("15551234567", "hello")),
    ]

    @pytest.mark.parametrize("method,args", DEVICE_CALLS)
    def test_every_device_call_refuses_an_agent_source(self, method, args):
        bridge = KDEConnectBridge(source="phone_cli")
        bridge.source = "fox"
        with pytest.raises(PhoneIsolationError):
            getattr(bridge, method)(*args)


class TestHonestSmsLimitation:
    """kdeconnect-cli cannot list SMS; the hub says so instead of faking it."""

    def test_bridge_reports_listing_as_unsupported(self):
        with pytest.raises(KDEConnectUnsupportedError, match="kdeconnect-cli"):
            KDEConnectBridge(source="phone_cli").list_sms()

    def test_messages_command_reports_the_real_limitation(self, capsys):
        policy = dict(DEFAULT_PERMISSIONS)
        policy[PhonePermision.MESSAGES] = True

        with pytest.raises(SystemExit) as exc:
            phone_cli.main(["messages"], permissions=policy)
        assert exc.value.code == 1
        assert "not supported" in capsys.readouterr().err

    def test_list_sms_command_reports_the_real_limitation(self, capsys):
        policy = dict(DEFAULT_PERMISSIONS)
        policy[PhonePermision.MESSAGES] = True

        with pytest.raises(SystemExit) as exc:
            phone_cli.main(["list-sms"], permissions=policy)
        assert exc.value.code == 1
        assert "not supported" in capsys.readouterr().err


class TestLeastPrivilegeContract:
    """The default policy is a documented least-privilege contract.

    Status and Files keep the hub usable. Notifications / Messages /
    Send Message are withheld by default and may be enabled only through
    an explicit policy grant; withholding them silently is not enough, and
    granting them silently is forbidden. Calls / Make Call stay withheld
    because KDE Connect cannot place calls. Any new permission, or any
    change to a grant, must consciously update this test together with
    the justification in permission.py.
    """

    def test_default_policy_is_exactly_the_documented_grants(self):
        assert DEFAULT_PERMISSIONS == {
            PhonePermision.Status: True,
            PhonePermision.NOTIFICATIONS: False,
            PhonePermision.MESSAGES: False,
            PhonePermision.FILES: True,
            PhonePermision.SEND_MESSAGE: False,
            PhonePermision.CALLS: False,
            PhonePermision.MAKE_CALL: False,
        }

    def test_is_allowed_denies_anything_missing_from_the_policy(self):
        assert is_allowed(PhonePermision.Status, {}) is False
        assert is_allowed(PhonePermision.Status, None) is True


class TestAgentCannotDriveTheCli:
    """The source label is attacker-controlled; the call stack is not."""

    def test_agent_module_cannot_drive_the_cli_with_a_trusted_label(self, capsys):
        sneaky = REPO_ROOT / "brain" / "sneaky_cli_caller.py"
        code = compile(
            "from phone.phone_cli import phone_cli\n"
            "try:\n"
            "    phone_cli.main(['status'], source='phone_cli')\n"
            "    outcome = 0\n"
            "except SystemExit as exc:\n"
            "    outcome = exc.code\n",
            str(sneaky),
            "exec",
        )
        namespace = {}
        exec(code, namespace)

        assert namespace["outcome"] == 1
        assert "isolated" in capsys.readouterr().err


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
