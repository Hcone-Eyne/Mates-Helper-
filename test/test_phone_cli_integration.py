"""Integration tests: phone CLI reachable from the main CLI.

Covers the wiring between main.py (menu) -> Cli.console.run_phone_hub ->
phone.phone_cli.phone_cli.main, including --device routing and the fact that
phone command failures must not kill the main CLI.
"""

import os
import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from phone.phone_cli import phone_cli
from test.test_phone_cli import MockBridge


def _console_module():
    """Import Cli.console, skipping if optional app deps are unavailable."""
    return pytest.importorskip("Cli.console")


def _drive_phone_hub(monkeypatch, console_mod, inputs, phone_main=None):
    """Run run_phone_hub with scripted user input and a patched phone CLI."""
    monkeypatch.setattr(console_mod.os, "system", lambda *args, **kwargs: 0)
    responses = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(responses))

    target = phone_main if phone_main is not None else MagicMock()
    with patch("phone.phone_cli.phone_cli.main", target):
        console_mod.run_phone_hub()
    return target


class TestPhoneCliReachableFromMainCli:

    def test_console_exposes_phone_runner(self):
        console_mod = _console_module()
        assert callable(getattr(console_mod, "run_phone_hub", None))

    def test_main_menu_lists_phone_option(self, monkeypatch):
        main_mod = pytest.importorskip("main")
        assert callable(getattr(main_mod, "run_phone_hub", None))

        from rich.console import Console

        buffer = StringIO()
        monkeypatch.setattr(
            main_mod, "console", Console(file=buffer, force_terminal=False, width=200)
        )
        main_mod.menu_bar()
        assert "Phone" in buffer.getvalue()

    def test_main_menu_routes_phone_choice_to_hub(self, monkeypatch, capsys):
        main_mod = pytest.importorskip("main")
        monkeypatch.setattr(main_mod.os, "system", lambda *args, **kwargs: 0)
        responses = iter(["5", "6"])
        monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(responses))

        with patch.object(main_mod, "run_phone_hub") as mock_hub:
            main_mod.run()

        mock_hub.assert_called_once_with()
        out = capsys.readouterr().out
        assert "Phone" in out
        assert "See you Soon Boss" in out


class TestPhoneHubCommandDispatch:

    def test_status_command_reaches_phone_cli(self, monkeypatch, capsys):
        console_mod = _console_module()
        mocked = _drive_phone_hub(monkeypatch, console_mod, ["status", "", "0"])
        mocked.assert_called_once_with(["status"])
        assert "Phone Hub" in capsys.readouterr().out

    def test_device_flag_is_preserved(self, monkeypatch):
        console_mod = _console_module()
        mocked = _drive_phone_hub(
            monkeypatch,
            console_mod,
            ["ping --device 8599f9fc623f4dcbb097f8048852939", "", "0"],
        )
        mocked.assert_called_once_with(
            ["ping", "--device", "8599f9fc623f4dcbb097f8048852939"]
        )

    def test_quoted_arguments_are_preserved(self, monkeypatch):
        console_mod = _console_module()
        mocked = _drive_phone_hub(
            monkeypatch,
            console_mod,
            ['share-text "hello world" --device abc', "", "0"],
        )
        mocked.assert_called_once_with(
            ["share-text", "hello world", "--device", "abc"]
        )

    def test_phone_cli_failure_does_not_exit_main_cli(self, monkeypatch, capsys):
        console_mod = _console_module()
        failing_main = MagicMock(side_effect=SystemExit(1))

        mocked = _drive_phone_hub(
            monkeypatch, console_mod, ["status", "", "0"], failing_main
        )
        mocked.assert_called_once_with(["status"])
        assert "Phone command failed" in capsys.readouterr().out

    def test_argparse_error_does_not_exit_main_cli(self, monkeypatch):
        console_mod = _console_module()
        failing_main = MagicMock(side_effect=SystemExit(2))

        _drive_phone_hub(
            monkeypatch, console_mod, ["not-a-command", "", "0"], failing_main
        )
        failing_main.assert_called_once_with(["not-a-command"])

    def test_back_command_returns_to_main_menu(self, monkeypatch, capsys):
        console_mod = _console_module()
        mocked = _drive_phone_hub(monkeypatch, console_mod, ["exit"])
        mocked.assert_not_called()
        assert "Exiting Phone Hub" in capsys.readouterr().out


class TestPhoneHubResilience:
    """Regressions found by stress testing the hub."""

    def _run_with(self, monkeypatch, console_mod, responses, phone_main=None):
        monkeypatch.setattr(console_mod.os, "system", lambda *args, **kwargs: 0)
        queued = iter(responses)

        def fake_input(*args, **kwargs):
            item = next(queued)
            if isinstance(item, BaseException):
                raise item
            return item

        monkeypatch.setattr("builtins.input", fake_input)
        target = phone_main if phone_main is not None else MagicMock()
        with patch("phone.phone_cli.phone_cli.main", target):
            console_mod.run_phone_hub()  # must never raise
        return target

    def test_eof_at_command_prompt_returns_to_menu(self, monkeypatch):
        console_mod = _console_module()
        target = self._run_with(
            monkeypatch, console_mod, [EOFError()]
        )
        target.assert_not_called()

    def test_eof_at_pause_prompt_returns_to_menu(self, monkeypatch):
        console_mod = _console_module()
        target = self._run_with(
            monkeypatch, console_mod, ["status", EOFError()]
        )
        target.assert_called_once_with(["status"])

    def test_keyboard_interrupt_returns_to_menu(self, monkeypatch):
        console_mod = _console_module()
        target = self._run_with(
            monkeypatch, console_mod, [KeyboardInterrupt()]
        )
        target.assert_not_called()

    def test_exit_keywords_are_case_insensitive(self, monkeypatch, capsys):
        console_mod = _console_module()
        target = self._run_with(monkeypatch, console_mod, ["Exit"])
        target.assert_not_called()
        assert "Exiting Phone Hub" in capsys.readouterr().out

    def test_unmatched_quote_is_reported_not_dispatched(self, monkeypatch, capsys):
        console_mod = _console_module()
        target = self._run_with(
            monkeypatch, console_mod, ['share-text "oops', "", "0"]
        )
        target.assert_not_called()
        out = capsys.readouterr().out
        assert "Couldn't parse that command" in out

    def test_empty_and_whitespace_input_loops_cleanly(self, monkeypatch):
        console_mod = _console_module()
        target = self._run_with(
            monkeypatch, console_mod, ["", "   ", "0"]
        )
        target.assert_not_called()


class TestPhoneCliArgvPlumbing:

    def test_main_uses_explicit_argv_not_sys_argv(self):
        bridge = MockBridge()
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge", return_value=bridge):
            with patch("sys.argv", ["not-the-phone-cli", "devices"]):
                phone_cli.main(["status"])
        assert bridge.calls == [("version", ())]

    def test_main_without_argv_still_reads_sys_argv(self):
        bridge = MockBridge()
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge", return_value=bridge):
            with patch("sys.argv", ["fox-phone", "devices"]):
                phone_cli.main()
        assert bridge.calls == [("list_devices", ())]


class TestDeviceFlagShortForm:

    def test_ping_accepts_short_device_flag(self):
        bridge = MockBridge()
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge", return_value=bridge):
            phone_cli.main(["ping", "-d", "abc123"])
        assert ("ping", ("abc123",)) in bridge.calls

    def test_share_accepts_short_device_flag(self, tmp_path):
        target = tmp_path / "note.txt"
        target.write_text("hi")
        bridge = MockBridge()
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge", return_value=bridge):
            phone_cli.main(["share", str(target), "-d", "abc123"])
        assert ("share", (str(target), "abc123")) in bridge.calls

    def test_long_device_flag_still_works(self):
        bridge = MockBridge()
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge", return_value=bridge):
            phone_cli.main(["ping", "--device", "abc123"])
        assert ("ping", ("abc123",)) in bridge.calls

    def test_both_spellings_map_to_the_same_option(self):
        bridge = MockBridge()
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge", return_value=bridge):
            phone_cli.main(["ping", "-d", "abc123", "--device", "def456"])
        assert ("ping", ("def456",)) in bridge.calls


class TestSubprocessTimeout:

    def test_bridge_passes_timeout_to_subprocess(self):
        from phone.bridge.kdeconnect import KDECONNECT_TIMEOUT, KDEConnectBridge

        with patch("shutil.which", return_value="/usr/bin/kdeconnect-cli"), \
                patch("subprocess.run") as run:
            run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
            assert KDEConnectBridge()._run("--ping") == "ok"
        assert run.call_args.kwargs["timeout"] == KDECONNECT_TIMEOUT

    def test_stuck_command_is_bounded_not_hung(self, tmp_path):
        import time

        from phone.bridge import kdeconnect
        from phone.bridge.kdeconnect import KDEConnectError, KDEConnectBridge

        script = tmp_path / "hang.sh"
        script.write_text("#!/bin/sh\nsleep 60\n")
        script.chmod(0o755)

        started = time.monotonic()
        with patch.object(kdeconnect, "KDECONNECT_TIMEOUT", 0.5):
            with pytest.raises(KDEConnectError, match="timed out"):
                KDEConnectBridge(binary=str(script))._run("--ping")
        assert time.monotonic() - started < 5

    def test_timeout_exits_cli_with_code_one(self):
        from phone.bridge.kdeconnect import KDEConnectError

        bridge = MockBridge()
        bridge.ping = MagicMock(side_effect=KDEConnectError("timed out after 30s: --ping"))
        with patch("phone.phone_cli.phone_cli.KDEConnectBridge", return_value=bridge):
            with pytest.raises(SystemExit) as exc:
                phone_cli.main(["ping", "-d", "abc123"])
        assert exc.value.code == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
