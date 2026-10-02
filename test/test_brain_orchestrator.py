"""Tests for brain orchestrator module."""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.orchestrator import (
    get_model,
    set_model,
    get_think,
    set_think,
    get_provider,
    set_provider,
    list_commands,
    handle_basic_command,
)


class TestModelManagement:
    """Test model get/set functions."""

    def test_get_model_default_none(self):
        # Reset to None
        import brain.orchestrator as orch
        original = orch._CURRENT_MODEL
        orch._CURRENT_MODEL = None
        try:
            assert get_model() is None
        finally:
            orch._CURRENT_MODEL = original

    def test_set_and_get_model(self):
        import brain.orchestrator as orch
        original = orch._CURRENT_MODEL
        try:
            set_model("test-model")
            assert get_model() == "test-model"
        finally:
            orch._CURRENT_MODEL = original


class TestThinkMode:
    """Test think mode get/set functions."""

    def test_get_think_default_false(self):
        import brain.orchestrator as orch
        original = orch.CURRENT_THINK
        orch.CURRENT_THINK = False
        try:
            assert get_think() is False
        finally:
            orch.CURRENT_THINK = original

    def test_set_think_true(self):
        import brain.orchestrator as orch
        original = orch.CURRENT_THINK
        try:
            result = set_think(True)
            assert get_think() is True
            assert "enabled" in result
        finally:
            orch.CURRENT_THINK = original

    def test_set_think_false(self):
        import brain.orchestrator as orch
        original = orch.CURRENT_THINK
        try:
            result = set_think(False)
            assert get_think() is False
            assert "disabled" in result
        finally:
            orch.CURRENT_THINK = original


class TestProviderManagement:
    """Test provider get/set functions."""

    def test_get_provider_default(self):
        import brain.orchestrator as orch
        original = orch.CURRENT_PROVIDER
        orch.CURRENT_PROVIDER = "ollama"
        try:
            assert get_provider() == "ollama"
        finally:
            orch.CURRENT_PROVIDER = original

    def test_get_provider_with_argument(self):
        assert get_provider("anthropic") == "anthropic"
        assert get_provider("OLLAMA") == "ollama"
        # get_provider doesn't strip whitespace (only set_provider does)
        assert get_provider("  Ollama  ") == "  ollama  "

    def test_set_provider_ollama(self):
        import brain.orchestrator as orch
        original = orch.CURRENT_PROVIDER
        try:
            result = set_provider("ollama")
            assert get_provider() == "ollama"
            assert result == "[Fox]: Provider set to ollama."
        finally:
            orch.CURRENT_PROVIDER = original

    def test_set_provider_anthropic(self):
        import brain.orchestrator as orch
        original = orch.CURRENT_PROVIDER
        try:
            result = set_provider("anthropic")
            assert get_provider() == "anthropic"
            assert result == "[Fox]: Provider set to anthropic."
        finally:
            orch.CURRENT_PROVIDER = original

    def test_set_provider_case_insensitive(self):
        import brain.orchestrator as orch
        original = orch.CURRENT_PROVIDER
        try:
            set_provider("OLLAMA")
            assert get_provider() == "ollama"
            set_provider("Anthropic")
            assert get_provider() == "anthropic"
        finally:
            orch.CURRENT_PROVIDER = original

    def test_set_provider_invalid(self):
        import brain.orchestrator as orch
        original = orch.CURRENT_PROVIDER
        try:
            result = set_provider("invalid")
            assert "Unsupported provider" in result
            # Should not change current provider
            assert get_provider() == original
        finally:
            orch.CURRENT_PROVIDER = original

    def test_set_provider_empty(self):
        import brain.orchestrator as orch
        original = orch.CURRENT_PROVIDER
        try:
            result = set_provider("")
            assert "Unsupported provider" in result
        finally:
            orch.CURRENT_PROVIDER = original

    def test_set_provider_none(self):
        import brain.orchestrator as orch
        original = orch.CURRENT_PROVIDER
        try:
            result = set_provider(None)
            assert "Unsupported provider" in result
        finally:
            orch.CURRENT_PROVIDER = original


class TestListCommands:
    """Test list_commands function."""

    def test_returns_expected_commands(self):
        commands = list_commands()
        assert isinstance(commands, list)
        assert "/help" in commands
        assert "/status" in commands
        assert "/ping" in commands
        assert "/tools" in commands
        assert "/quit" in commands
        assert len(commands) == 5


class TestHandleBasicCommand:
    """Test handle_basic_command function."""

    def test_empty_string(self):
        result = handle_basic_command("")
        assert result == "[Fox]: Empty Task, Nothin to Show....."

    def test_whitespace_only(self):
        result = handle_basic_command("   ")
        assert result == "[Fox]: Empty Task, Nothin to Show....."

    def test_help_aliases(self):
        for cmd in ["help", "/help", "cmds", "commands"]:
            result = handle_basic_command(cmd)
            assert "Available commands" in result
            assert "/help" in result
            assert "/status" in result

    def test_help_case_insensitive(self):
        result = handle_basic_command("HELP")
        assert "Available commands" in result

    def test_status(self):
        for cmd in ["status", "/status"]:
            result = handle_basic_command(cmd)
            assert "Orchestrator is online" in result

    def test_ping(self):
        for cmd in ["ping", "/ping"]:
            result = handle_basic_command(cmd)
            assert result == "[Fox]: pong"

    def test_tools(self):
        for cmd in ["tools", "/tools"]:
            result = handle_basic_command(cmd)
            assert "Available tools" in result

    def test_quit_aliases(self):
        for cmd in ["quit", "/quit", "exit"]:
            result = handle_basic_command(cmd)
            assert "Command mode closed" in result

    def test_unknown_command_returns_none(self):
        result = handle_basic_command("unknown_command")
        assert result is None

    def test_unknown_command_with_slash(self):
        result = handle_basic_command("/unknown")
        assert result is None


class TestRunTask:
    """Test run_task function (mocked)."""

    @patch("brain.orchestrator.FoxAgent")
    def test_run_task_greeting_uses_conversation(self, mock_fox_agent):
        mock_agent = MagicMock()
        mock_agent.ask.return_value = "Hi! How can I help?"
        mock_fox_agent.return_value = mock_agent

        from brain.orchestrator import run_task
        result = run_task("Hi")

        assert result == "Hi! How can I help?"
        mock_agent.ask.assert_called_once_with("Hi")

    @patch("brain.orchestrator.build_runtime")
    @patch("brain.orchestrator.get_provider", return_value="ollama")
    def test_run_task_ollama(self, mock_get_provider, mock_build_runtime):
        from agent.fox.runtime.runtime import RuntimeResult, SelinaResult
        mock_runtime = MagicMock()
        mock_selina_result = SelinaResult(
            success=True,
            expanded_task="test",
            interpretation="test",
            action="test",
            result="Test response",
            error=None
        )
        mock_runtime.handle.return_value = RuntimeResult(
            user_request="test task",
            julie_result=MagicMock(),
            annie_result=MagicMock(),
            selina_result=mock_selina_result,
            gwen_result=MagicMock(),
            final_result=mock_selina_result
        )
        mock_build_runtime.return_value = mock_runtime

        from brain.orchestrator import run_task
        result = run_task("test task")

        assert result == "Test response"
        mock_build_runtime.assert_called_once()
        mock_runtime.handle.assert_called_once_with("test task")

    @patch("brain.orchestrator.build_runtime")
    @patch("brain.orchestrator.get_provider", return_value="ollama")
    def test_run_task_action_reaches_fox_club(self, mock_get_provider, mock_build_runtime):
        from agent.fox.runtime.runtime import RuntimeResult, SelinaResult

        mock_runtime = MagicMock()
        mock_selina_result = SelinaResult(
            success=True,
            expanded_task="list files",
            interpretation="list files",
            action="list_directory",
            result="workspace/file.txt",
            error=None,
        )
        mock_runtime.handle.return_value = RuntimeResult(
            user_request="list files",
            julie_result=MagicMock(),
            annie_result=MagicMock(),
            selina_result=mock_selina_result,
            gwen_result=MagicMock(),
            final_result=mock_selina_result,
        )
        mock_build_runtime.return_value = mock_runtime

        from brain.orchestrator import run_task
        result = run_task("list files")

        assert result == "workspace/file.txt"
        mock_build_runtime.assert_called_once()
        mock_runtime.handle.assert_called_once_with("list files")

    @patch("brain.orchestrator.build_runtime")
    @patch("brain.orchestrator.get_provider", return_value="ollama")
    def test_run_task_never_returns_none_for_empty_task_result(
        self,
        mock_get_provider,
        mock_build_runtime,
    ):
        from agent.fox.runtime.runtime import RuntimeResult, SelinaResult

        mock_runtime = MagicMock()
        mock_selina_result = SelinaResult(
            success=True,
            expanded_task="do nothing",
            interpretation="do nothing",
            action="noop",
            result=None,
            error=None,
        )
        mock_runtime.handle.return_value = RuntimeResult(
            user_request="do nothing",
            julie_result=MagicMock(),
            annie_result=MagicMock(),
            selina_result=mock_selina_result,
            gwen_result=MagicMock(),
            final_result=mock_selina_result,
        )
        mock_build_runtime.return_value = mock_runtime

        from brain.orchestrator import run_task
        result = run_task("do nothing")

        assert result is not None
        assert "None" not in result

    @patch("brain.orchestrator.FoxAgent")
    @patch("brain.orchestrator.get_provider", return_value="anthropic")
    @patch("brain.orchestrator._get_anthropic_client")
    def test_run_task_anthropic_fallback_to_ollama(self, mock_get_client, mock_get_provider, mock_fox_agent):
        mock_get_client.side_effect = RuntimeError("No API key")
        mock_agent = MagicMock()
        mock_agent.ask.return_value = "Fallback response"
        mock_fox_agent.return_value = mock_agent

        from brain.orchestrator import run_task
        result = run_task("test task")

        assert result == "Fallback response"
        mock_fox_agent.assert_called_once()

    @patch("brain.orchestrator.get_provider", return_value="unknown")
    def test_run_task_unknown_provider(self, mock_get_provider):
        from brain.orchestrator import run_task
        result = run_task("test task")
        assert "not configured yet" in result

    def test_run_task_basic_command_intercepted(self):
        from brain.orchestrator import run_task
        result = run_task("/ping")
        assert result == "[Fox]: pong"

    def test_run_task_empty_string(self):
        from brain.orchestrator import run_task
        result = run_task("")
        assert result == "[Fox]: Empty Task, Nothin to Show....."


def _ollama_runtime_result(task: str):
    from agent.fox.runtime.runtime import RuntimeResult, SelinaResult

    selina = SelinaResult(
        success=True,
        expanded_task=task,
        interpretation=task,
        action="test",
        result="Test response",
        error=None,
    )
    return RuntimeResult(
        user_request=task,
        julie_result=MagicMock(),
        annie_result=MagicMock(),
        selina_result=selina,
        gwen_result=MagicMock(),
        final_result=selina,
    )


class TestRuntimeRootingAndModelConfig:
    """Regression tests for the runtime/model configuration findings."""

    @patch("brain.orchestrator.build_runtime")
    @patch("brain.orchestrator.get_provider", return_value="ollama")
    def test_fox_club_executor_is_not_rooted_in_the_repo(self, mock_provider, mock_build):
        from brain.orchestrator import run_task

        mock_build.return_value = MagicMock(
            handle=MagicMock(return_value=_ollama_runtime_result("test task"))
        )

        assert run_task("test task") == "Test response"

        # Passing target_dir="." made the Fox Club executor able to write and
        # delete at repository root; leaving it unset roots it in Fox Space.
        assert mock_build.call_args.kwargs.get("target_dir") is None

    @patch("brain.orchestrator._get_anthropic_client")
    @patch("brain.orchestrator.get_provider", return_value="anthropic")
    def test_anthropic_model_comes_from_configuration(self, mock_provider, mock_client):
        import brain.orchestrator as orch
        from brain.orchestrator import run_task

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "hello"

        response = MagicMock()
        response.stop_reason = "end_turn"
        response.content = [text_block]

        client = MagicMock()
        client.messages.create.return_value = response
        mock_client.return_value = client

        with patch.object(orch, "ANTHROPIC_MODEL", "claude-custom-test"):
            assert run_task("test task") == "hello"

        assert client.messages.create.call_args.kwargs["model"] == "claude-custom-test"

    def test_anthropic_model_has_a_documented_default(self):
        import brain.orchestrator as orch

        assert isinstance(orch.ANTHROPIC_MODEL, str)
        assert orch.ANTHROPIC_MODEL == "claude-sonnet-5"

    def test_provider_state_is_not_silently_reassigned(self):
        # CURRENT_PROVIDER used to be assigned twice at module level, which
        # made the second assignment the real one.
        import re

        import brain.orchestrator as orch

        source = open(orch.__file__).read()
        module_level = re.findall(r"^CURRENT_PROVIDER = ", source, re.MULTILINE)
        assert len(module_level) == 1


class TestAnthropicToolLoopIsBounded:
    """Regression for the unbounded Anthropic tool loop.

    The loop used to be `while True`. A model that only ever answers with
    stop_reason='tool_use' drove it past 61 API calls with no termination.
    """

    @staticmethod
    def _tool_use_response():
        block = MagicMock()
        block.type = "tool_use"
        block.name = "schedule_view"
        block.input = {"query": "monday"}
        block.id = "toolu_1"

        response = MagicMock()
        response.stop_reason = "tool_use"
        response.content = [block]
        return response

    @patch("brain.orchestrator.dispatcher", return_value="ok")
    @patch("brain.orchestrator.get_provider", return_value="anthropic")
    @patch("brain.orchestrator._get_anthropic_client")
    def test_loop_stops_at_the_turn_limit(
        self, mock_get_client, mock_get_provider, mock_dispatcher
    ):
        from brain.orchestrator import MAX_TOOL_TURNS, run_task

        client = MagicMock()
        client.messages.create.return_value = self._tool_use_response()
        mock_get_client.return_value = client

        result = run_task("show my schedule")

        # Bounded, and it terminates on its own rather than looping forever.
        assert MAX_TOOL_TURNS == 5
        assert client.messages.create.call_count == MAX_TOOL_TURNS
        assert isinstance(result, str) and result
        assert "Stopped after" in result

    @patch("brain.orchestrator.get_provider", return_value="anthropic")
    @patch("brain.orchestrator._get_anthropic_client")
    def test_final_answer_still_wins_before_the_limit(
        self, mock_get_client, mock_get_provider
    ):
        from brain.orchestrator import run_task

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "the answer"

        final = MagicMock()
        final.stop_reason = "end_turn"
        final.content = [text_block]

        client = MagicMock()
        client.messages.create.side_effect = [
            self._tool_use_response(),
            final,
        ]
        mock_get_client.return_value = client

        assert run_task("show my schedule") == "the answer"
        assert client.messages.create.call_count == 2

    @patch("brain.orchestrator.dispatcher", side_effect=RuntimeError("tool exploded"))
    @patch("brain.orchestrator.get_provider", return_value="anthropic")
    @patch("brain.orchestrator._get_anthropic_client")
    def test_a_failing_tool_does_not_hang_the_loop(
        self, mock_get_client, mock_get_provider, mock_dispatcher
    ):
        # A raising dispatcher used to escape run_task; it must still not be
        # able to spin the API loop.
        from brain.orchestrator import MAX_TOOL_TURNS, run_task

        client = MagicMock()
        client.messages.create.return_value = self._tool_use_response()
        mock_get_client.return_value = client

        with pytest.raises(RuntimeError, match="tool exploded"):
            run_task("show my schedule")

        assert client.messages.create.call_count <= MAX_TOOL_TURNS
