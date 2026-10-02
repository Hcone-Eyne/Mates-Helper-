"""Tests for the interactive menus in Cli/console.py.

Covers the bugs found by the CLI audit: an unreachable ValueError handler, a
KeyboardInterrupt that did not actually leave the finance menu, a
FileNotFoundError handler that referenced an unbound `image_path`, and Phone
Hub panel copy that promised message reading the CLI cannot do.
"""

import os
import sys
from io import StringIO
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rich.console import Console


def _console_module():
    return pytest.importorskip("Cli.console")


def _drive(monkeypatch, console_mod, inputs, target):
    """Run `target` with scripted input and a buffered rich console."""
    queue = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(queue))
    monkeypatch.setattr(console_mod.os, "system", lambda *a, **k: 0)

    buffer = StringIO()
    monkeypatch.setattr(
        console_mod, "console", Console(file=buffer, force_terminal=False, width=200)
    )
    target()
    return buffer.getvalue()


class TestFinanceBotMenu:

    def test_value_error_is_reported_and_loop_continues(self, monkeypatch):
        console_mod = _console_module()

        with patch("Cli.console.operation_finder", side_effect=ValueError("bad")):
            out = _drive(
                monkeypatch,
                console_mod,
                ["1", "not-a-sum", "", "0"],
                console_mod.run_finance_bot,
            )

        assert "Invalid Input" in out
        # the menu came back and the user could leave with 0
        assert "Exiting Finance Bot" in out

    def test_keyboard_interrupt_returns_to_main_menu(self, monkeypatch):
        console_mod = _console_module()

        with patch("Cli.console.operation_finder", side_effect=KeyboardInterrupt):
            with patch("Cli.console.memory_lister") as mock_lister:
                out = _drive(
                    monkeypatch,
                    console_mod,
                    ["1", "whatever"],
                    console_mod.run_finance_bot,
                )

        assert "Exiting Finance Bot" in out
        mock_lister.assert_called_once_with()

    def test_generic_error_is_reported(self, monkeypatch):
        console_mod = _console_module()

        with patch("Cli.console.operation_finder", side_effect=RuntimeError("boom")):
            out = _drive(
                monkeypatch,
                console_mod,
                ["1", "1+1", "", "0"],
                console_mod.run_finance_bot,
            )

        assert "Error Occured: boom" in out

    def test_plain_exit_returns_immediately(self, monkeypatch):
        console_mod = _console_module()
        out = _drive(
            monkeypatch, console_mod, ["0"], console_mod.run_finance_bot
        )
        assert "Exiting Finance Bot" in out


class TestSchedulerMenu:

    def test_missing_schedule_file_does_not_raise_name_error(self, monkeypatch):
        """image_path used to be unbound when choice 1 failed."""
        console_mod = _console_module()

        with patch(
            "Cli.console.pd.read_csv", side_effect=FileNotFoundError("no csv")
        ):
            out = _drive(
                monkeypatch,
                console_mod,
                ["1", "", "0"],
                console_mod.run_scheduler,
            )

        assert "Couldn't find a file" in out

    def test_bad_upload_path_is_reported(self, monkeypatch):
        console_mod = _console_module()

        with patch(
            "Cli.console.extract_table", side_effect=FileNotFoundError("no image")
        ):
            out = _drive(
                monkeypatch,
                console_mod,
                ["2", "/no/such/image.png", "", "0"],
                console_mod.run_scheduler,
            )

        assert "/no/such/image.png" in out


class TestFoxAgentMenu:
    """The agent menu must survive an unavailable Ollama.

    FoxConversationManager refuses to start when no model can be found, and it
    used to be built outside any handler - picking Fox Agent then took the
    whole CLI down with a traceback instead of returning to the menu.
    """

    def _run_without_ollama(self, monkeypatch, console_mod):
        queue = iter([""])  # one pause before the menu comes back
        monkeypatch.setattr("builtins.input", lambda *a, **k: next(queue))
        monkeypatch.setattr(console_mod.os, "system", lambda *a, **k: 0)

        buffer = StringIO()
        monkeypatch.setattr(
            console_mod, "console", Console(file=buffer, force_terminal=False, width=200)
        )

        no_models = {
            "installed": True,
            "binary": "/usr/bin/ollama",
            "host": "http://127.0.0.1:11434",
            "running": False,
            "models": [],
        }
        with patch(
            "agent.fox.conversation.manager.discover_ollama", return_value=no_models
        ), patch.object(console_mod, "get_model", return_value=None):
            console_mod.run_fox_agent()

        return buffer.getvalue()

    def test_missing_ollama_model_returns_to_the_main_menu(self, monkeypatch):
        console_mod = _console_module()
        out = self._run_without_ollama(monkeypatch, console_mod)

        assert "No Ollama model is found" in out
        assert "Returning to the main menu" in out

    def test_missing_ollama_does_not_claim_a_provider_switch(self, monkeypatch):
        # The failure must be reported, not papered over by silently moving
        # the user onto another provider.
        console_mod = _console_module()
        out = self._run_without_ollama(monkeypatch, console_mod)

        assert "anthropic" not in out.lower()
        assert "switching" not in out.lower()

    def test_missing_ollama_does_not_open_the_agent_panel(self, monkeypatch):
        console_mod = _console_module()
        out = self._run_without_ollama(monkeypatch, console_mod)

        # The Connected panel is only drawn once a conversation manager exists.
        assert "Type /provider" not in out


class TestPhoneHubPanelIsHonest:

    def _hub_text(self, monkeypatch, console_mod):
        monkeypatch.setattr(console_mod.os, "system", lambda *a, **k: 0)
        monkeypatch.setattr("builtins.input", lambda *a, **k: "exit")

        buffer = StringIO()
        monkeypatch.setattr(
            console_mod, "console", Console(file=buffer, force_terminal=False, width=200)
        )
        with patch("phone.phone_cli.phone_cli.main") as phone_main:
            console_mod.run_phone_hub()
        phone_main.assert_not_called()
        return buffer.getvalue()

    def test_panel_does_not_promise_message_reading(self, monkeypatch):
        console_mod = _console_module()
        out = self._hub_text(monkeypatch, console_mod)
        assert "read from the phone" not in out

    def test_panel_states_the_kdeconnect_cli_limitation(self, monkeypatch):
        console_mod = _console_module()
        out = self._hub_text(monkeypatch, console_mod)
        assert "not supported by kdeconnect-cli" in out

    def test_panel_labels_permissions_as_local_policy(self, monkeypatch):
        console_mod = _console_module()
        out = self._hub_text(monkeypatch, console_mod)
        assert "local permission policy" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
