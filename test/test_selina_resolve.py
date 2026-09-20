"""Tests for Selina's _resolve_action and Selina class."""

import sys
import os
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.selina.selina import _resolve_action, SUPPORTED_ACTIONS, Selina, SelinaResult
from agent.julie.julie import JulieResult
from agent.annie.annie import AnnieResult


class TestResolveAction:
    """Test _resolve_action function."""

    def test_resolve_organise_folder(self):
        assert _resolve_action(["organise my files"]) == "organise_folder"
        assert _resolve_action(["organize folder"]) == "organise_folder"
        assert _resolve_action(["sort files"]) == "organise_folder"
        assert _resolve_action(["categorize documents"]) == "organise_folder"
        assert _resolve_action(["category"]) == "organise_folder"

    def test_resolve_list_directory(self):
        assert _resolve_action(["list files"]) == "list_directory"
        assert _resolve_action(["show contents"]) == "list_directory"
        assert _resolve_action(["display directory"]) == "list_directory"
        assert _resolve_action(["contents"]) == "list_directory"
        assert _resolve_action(["directory"]) == "list_directory"

    def test_resolve_find_files(self):
        assert _resolve_action(["search for files"]) == "find_files"
        assert _resolve_action(["find document"]) == "find_files"
        assert _resolve_action(["locate file"]) == "find_files"
        assert _resolve_action(["look for"]) == "find_files"

    def test_case_insensitive(self):
        assert _resolve_action(["ORGANISE"]) == "organise_folder"
        assert _resolve_action(["List"]) == "list_directory"
        assert _resolve_action(["FiNd"]) == "find_files"

    def test_whole_word_matching(self):
        # "organise" should match but "reorganise" should not (if not a keyword)
        assert _resolve_action(["organise"]) == "organise_folder"
        # The keywords are matched as whole words, so partial matches shouldn't work
        # But "reorganise" contains "organise" as a substring - let's check
        # Actually the regex uses \b (word boundary), so "reorganise" won't match "organise"
        assert _resolve_action(["reorganise"]) == ""  # no match

    def test_first_match_wins(self):
        # If multiple requirements match different actions, first one wins
        assert _resolve_action(["list files", "organise folder"]) == "list_directory"
        assert _resolve_action(["organise folder", "list files"]) == "organise_folder"

    def test_scans_all_requirements(self):
        # Should scan all requirements until a match is found
        assert _resolve_action(["unknown", "list files"]) == "list_directory"
        assert _resolve_action(["unknown1", "unknown2", "organise"]) == "organise_folder"

    def test_empty_requirements_returns_empty(self):
        assert _resolve_action([]) == ""
        assert _resolve_action([""]) == ""
        assert _resolve_action(["   "]) == ""

    def test_no_match_returns_empty(self):
        assert _resolve_action(["unknown keyword"]) == ""
        assert _resolve_action(["random", "words"]) == ""

    def test_supported_actions_complete(self):
        # Verify all expected actions are in SUPPORTED_ACTIONS
        assert "organise_folder" in SUPPORTED_ACTIONS
        assert "list_directory" in SUPPORTED_ACTIONS
        assert "find_files" in SUPPORTED_ACTIONS
        assert len(SUPPORTED_ACTIONS) == 3

    def test_action_keywords_not_empty(self):
        for action, keywords in SUPPORTED_ACTIONS.items():
            assert len(keywords) > 0, f"{action} has no keywords"
            for kw in keywords:
                assert isinstance(kw, str)
                assert kw.strip()


class TestSelinaExecute:
    """Test Selina.execute method."""

    def test_invalid_julie_result_raises(self):
        executor = MagicMock()
        selina = Selina(executor)
        with pytest.raises(TypeError, match="Input must be a JulieResult"):
            selina.execute("not a JulieResult")

    def test_empty_expanded_task_returns_failure(self):
        executor = MagicMock()
        selina = Selina(executor)
        julie_result = JulieResult(
            user_request="test",
            context=None,
            expanded_task="",
            plan=["step"],
            uncertainty=[],
            raw_response="raw"
        )
        result = selina.execute(julie_result)
        assert result.success is False
        assert result.error == "Expanded task is empty."
        assert result.action == ""

    def test_whitespace_expanded_task_returns_failure(self):
        executor = MagicMock()
        selina = Selina(executor)
        julie_result = JulieResult(
            user_request="test",
            context=None,
            expanded_task="   ",
            plan=["step"],
            uncertainty=[],
            raw_response="raw"
        )
        result = selina.execute(julie_result)
        assert result.success is False
        assert result.error == "Expanded task is empty."

    def test_no_action_from_plan_returns_failure(self):
        executor = MagicMock()
        selina = Selina(executor)
        julie_result = JulieResult(
            user_request="test",
            context=None,
            expanded_task="do something unknown",
            plan=["unknown step"],
            uncertainty=[],
            raw_response="raw"
        )
        result = selina.execute(julie_result)
        assert result.success is False
        assert "Could not determine an action" in result.error

    def test_executor_exception_returns_failure(self):
        executor = MagicMock()
        executor.execute.side_effect = RuntimeError("Executor failed")
        selina = Selina(executor)
        julie_result = JulieResult(
            user_request="test",
            context=None,
            expanded_task="list files",
            plan=["list files"],
            uncertainty=[],
            raw_response="raw"
        )
        result = selina.execute(julie_result)
        assert result.success is False
        assert "Executor failed" in result.error

    def test_successful_execution(self):
        executor = MagicMock()
        executor.execute.return_value = {"summary": "success"}
        selina = Selina(executor)
        julie_result = JulieResult(
            user_request="list files",
            context=None,
            expanded_task="list files in directory",
            plan=["list files"],
            uncertainty=[],
            raw_response="raw"
        )
        result = selina.execute(julie_result)
        assert result.success is True
        assert result.action == "list_directory"
        assert result.result == {"summary": "success"}


class TestSelinaExecuteFromAnnie:
    """Test Selina.execute_from_annie method."""

    def test_invalid_annie_result_raises(self):
        executor = MagicMock()
        selina = Selina(executor)
        with pytest.raises(TypeError, match="Input must be an AnnieResult"):
            selina.execute_from_annie("not an AnnieResult")

    def test_empty_technical_handoff_returns_failure(self):
        executor = MagicMock()
        selina = Selina(executor)
        annie_result = AnnieResult(
            user_request="test",
            interpretation="interp",
            requirements=[],
            constraints=[],
            technical_handoff="",
            clarification_needed=[],
            raw_response="raw"
        )
        result = selina.execute_from_annie(annie_result)
        assert result.success is False
        assert "technical_handoff is empty" in result.error

    def test_no_action_from_requirements_returns_failure(self):
        executor = MagicMock()
        selina = Selina(executor)
        annie_result = AnnieResult(
            user_request="test",
            interpretation="interp",
            requirements=["unknown"],
            constraints=[],
            technical_handoff="handoff",
            clarification_needed=[],
            raw_response="raw"
        )
        result = selina.execute_from_annie(annie_result)
        assert result.success is False
        assert "Could not determine an action" in result.error

    def test_explicit_action_overrides_requirements(self):
        executor = MagicMock()
        executor.execute.return_value = {"result": "ok"}
        selina = Selina(executor)
        annie_result = AnnieResult(
            user_request="test",
            interpretation="interp",
            requirements=["unknown"],
            constraints=[],
            technical_handoff="handoff",
            clarification_needed=[],
            raw_response="raw"
        )
        result = selina.execute_from_annie(annie_result, action="list_directory")
        assert result.success is True
        assert result.action == "list_directory"
        # Verify executor was called with the explicit action
        call_args = executor.execute.call_args
        assert call_args[1]["action"] == "list_directory"

    def test_executor_exception_returns_failure(self):
        executor = MagicMock()
        executor.execute.side_effect = RuntimeError("Exec failed")
        selina = Selina(executor)
        annie_result = AnnieResult(
            user_request="test",
            interpretation="interp",
            requirements=["list files"],
            constraints=[],
            technical_handoff="handoff",
            clarification_needed=[],
            raw_response="raw"
        )
        result = selina.execute_from_annie(annie_result)
        assert result.success is False
        assert "Exec failed" in result.error


class TestSelinaInterpret:
    """Test Selina._interpret static method."""

    def test_interprets_task_with_steps(self):
        julie_result = JulieResult(
            user_request="test",
            context=None,
            expanded_task="list files",
            plan=["step 1", "step 2"],
            uncertainty=[],
            raw_response="raw"
        )
        interpretation = Selina._interpret(julie_result)
        assert "Task: list files" in interpretation
        assert "Steps: step 1; step 2" in interpretation

    def test_interprets_task_without_steps(self):
        julie_result = JulieResult(
            user_request="test",
            context=None,
            expanded_task="list files",
            plan=[],
            uncertainty=[],
            raw_response="raw"
        )
        interpretation = Selina._interpret(julie_result)
        assert "Task: list files" in interpretation
        assert "No steps provided" in interpretation


class TestSelinaDetermineAction:
    """Test Selina._determine_action static method."""

    def test_determines_action_from_plan(self):
        julie_result = JulieResult(
            user_request="test",
            context=None,
            expanded_task="task",
            plan=["list files"],
            uncertainty=[],
            raw_response="raw"
        )
        action = Selina._determine_action(julie_result)
        assert action == "list_directory"

    def test_empty_plan_returns_empty(self):
        julie_result = JulieResult(
            user_request="test",
            context=None,
            expanded_task="task",
            plan=[],
            uncertainty=[],
            raw_response="raw"
        )
        action = Selina._determine_action(julie_result)
        assert action == ""

    def test_no_matching_action_returns_empty(self):
        julie_result = JulieResult(
            user_request="test",
            context=None,
            expanded_task="task",
            plan=["unknown step"],
            uncertainty=[],
            raw_response="raw"
        )
        action = Selina._determine_action(julie_result)
        assert action == ""


from unittest.mock import MagicMock