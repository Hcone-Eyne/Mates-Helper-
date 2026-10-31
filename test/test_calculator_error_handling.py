"""Focused tests for calculator error-handling consistency.

operation_finder never raises for token-less input ("abc", "", whitespace) -
it returns None - but it DOES raise for malformed expressions:
ZeroDivisionError ("5/0"), ValueError ("5++3", "+5"), and IndexError ("5+").
Every entry point must handle both shapes so the same bad expression cannot
crash one path while another replies with a [Fox]-style message:

* agent/brain paths: dispatch() already converts exceptions into
  "[Fox]: Tool 'finance_calculate' error: ..." strings.
* MCP path: the finance_calculate tool must not let exceptions escape as raw
  tool errors; it returns "[Fox]: Calculator error: ...".
* CLI path: the finance menu must not display a misleading
  "Result: None" (a success-looking value) for token-less input.

Valid calculations must keep working and be stored exactly once everywhere.
"""

import os
import sys
from io import StringIO
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rich.console import Console

BAD_EXPRESSIONS = ["5/0", "5++3", "5+", "", "abc"]


@pytest.fixture(autouse=True)
def isolated_memory_log():
    """Keep the process-global finance log empty; restore its state after."""
    from Memory import memory_storer as m

    saved = list(m.memory_log)
    m.memory_log.clear()
    yield m
    with m._memory_lock:
        m.memory_log[:] = saved


@pytest.fixture
def console_module():
    return pytest.importorskip("Cli.console")


class TestMcpFinanceCalculateErrorContract:
    """Mcp_plugins.mcp_server.finance_calculate must mirror the [Fox]
    message contract used by the agent and CLI entry points instead of
    raising evaluator exceptions."""

    def _tool(self):
        server = pytest.importorskip("mcp_plugins.mcp_server")
        return server.finance_calculate

    @pytest.mark.parametrize("expression", ["5/0", "5++3", "5+"])
    def test_malformed_expression_returns_error_not_exception(self, expression):
        result = self._tool()(expression)
        assert isinstance(result, str)
        assert result.startswith("[Fox]: Calculator error: ")

    def test_tokenless_expression_still_reports_invalid(self):
        assert self._tool()("abc") == "[Fox]: Invalid expression. Use digits!"
        assert self._tool()("") == "[Fox]: Invalid expression. Use digits!"

    @pytest.mark.parametrize("expression", BAD_EXPRESSIONS)
    def test_errors_never_pollute_memory(self, isolated_memory_log, expression):
        self._tool()(expression)
        assert isolated_memory_log.memory_log == []

    def test_valid_calculation_still_works_and_is_stored(self, isolated_memory_log):
        result = self._tool()("2+3*4")
        assert result == "[Fox]: Result ->14"
        assert isolated_memory_log.memory_log == [{"expression": "2+3*4", "result": 14}]

    def test_division_still_works(self, isolated_memory_log):
        assert self._tool()("20/4") == "[Fox]: Result ->5.0"


class TestAgentErrorContract:
    """dispatch() already caught evaluator exceptions: pin that contract so
    the [Fox] error string shape cannot regress."""

    def test_division_by_zero_is_reported_not_raised(self):
        from agent.ollama.tools import dispatch

        assert (
            dispatch("finance_calculate", expression="5/0")
            == "[Fox]: Tool 'finance_calculate' error: division by zero"
        )

    def test_malformed_expression_is_reported_not_raised(self):
        from agent.ollama.tools import dispatch

        assert dispatch("finance_calculate", expression="5+").startswith(
            "[Fox]: Tool 'finance_calculate' error: "
        )

    @pytest.mark.parametrize("expression", BAD_EXPRESSIONS)
    def test_errors_never_pollute_memory(self, isolated_memory_log, expression):
        from agent.ollama.tools import dispatch

        dispatch("finance_calculate", expression=expression)
        assert isolated_memory_log.memory_log == []

    def test_valid_calculation_still_works_and_is_stored(self, isolated_memory_log):
        from agent.ollama.tools import dispatch

        assert dispatch("finance_calculate", expression="2+3") == "[Fox]: Result -> 5"
        assert isolated_memory_log.memory_log == [{"expression": "2+3", "result": 5}]


class TestBrainDispatcherErrorContract:
    """brain.tools.dispatcher delegates to the agent registry, so a Brain
    caller must get the same error string as a direct agent caller."""

    @pytest.mark.parametrize("expression", ["5/0", "5++3", "5+", "abc"])
    def test_bad_expressions_return_fox_error_strings(self, expression):
        from brain.tools import dispatcher

        result = dispatcher("finance_calculate", {"expression": expression})
        assert isinstance(result, str)
        assert result.startswith("[Fox]:")

    def test_valid_calculation_still_works(self, isolated_memory_log):
        from brain.tools import dispatcher

        assert dispatcher("finance_calculate", {"expression": "2+2"}) == "[Fox]: Result -> 4"


def _drive_finance_menu(monkeypatch, console_mod, inputs):
    """Run run_finance_bot with scripted input and a buffered rich console."""
    queue = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(queue))
    monkeypatch.setattr(console_mod.os, "system", lambda *a, **k: 0)

    buffer = StringIO()
    monkeypatch.setattr(
        console_mod,
        "console",
        Console(file=buffer, force_terminal=False, width=200),
    )
    console_mod.run_finance_bot()
    return buffer.getvalue()


class TestCliFinanceMenuErrorContract:
    """The CLI finance menu converts exceptions via its handlers, but used to
    display token-less invalid input as a success-looking "Result: None"."""

    def test_invalid_expression_does_not_show_result_none(
        self, monkeypatch, console_module, isolated_memory_log, capsys
    ):
        with patch.object(console_module, "memory_lister"):
            out = _drive_finance_menu(
                monkeypatch, console_module, ["1", "abc", "", "0"]
            )

        assert "[Fox]: Result:" not in out
        assert isolated_memory_log.memory_log == []
        # operation_finder prints its own hint on stdout (via plain print).
        assert "Invalid expression" in capsys.readouterr().out

    def test_division_by_zero_is_reported_and_loop_survives(
        self, monkeypatch, console_module, isolated_memory_log
    ):
        """ZeroDivisionError reaches the menu's generic Exception handler."""
        with patch.object(console_module, "memory_lister"):
            out = _drive_finance_menu(
                monkeypatch, console_module, ["1", "5/0", "", "0"]
            )

        assert "Error Occured: division by zero" in out
        assert isolated_memory_log.memory_log == []

    def test_trailing_operator_is_reported_and_loop_survives(
        self, monkeypatch, console_module, isolated_memory_log
    ):
        with patch.object(console_module, "memory_lister"):
            out = _drive_finance_menu(
                monkeypatch, console_module, ["1", "5+", "", "0"]
            )

        assert "Error Occured: list index out of range" in out
        assert isolated_memory_log.memory_log == []

    def test_valid_expression_pushes_exactly_one_entry(
        self, monkeypatch, console_module, isolated_memory_log
    ):
        with patch.object(console_module, "memory_lister"):
            _drive_finance_menu(
                monkeypatch, console_module, ["1", "12+3*2", "", "0"]
            )

        assert isolated_memory_log.memory_log == [{"expression": "12+3*2", "result": 18}]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
