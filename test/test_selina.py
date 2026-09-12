"""Focused tests for Selina's execution logic with JulieResult input."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from agent.julie.julie import JulieResult
from agent.selina.selina import Selina, SelinaResult


class RecordingExecutor:
    """Fake executor that records calls and returns a preset result."""

    def __init__(self, result="done"):
        self.result = result
        self.calls = []

    def execute(self, action, arguments):
        self.calls.append({"action": action, "arguments": arguments})
        return self.result


class RaisingExecutor:
    """Fake executor that always raises."""

    def execute(self, action, arguments):
        raise RuntimeError("Executor failed on purpose")


def _make_julie_result(**overrides) -> JulieResult:
    defaults = {
        "user_request": "read the config file",
        "context": None,
        "expanded_task": "Read and return the contents of config.yaml",
        "plan": ["read_file", "parse_yaml"],
        "uncertainty": ["file might not exist"],
        "raw_response": "{}",
    }
    defaults.update(overrides)
    return JulieResult(**defaults)


# --- success cases ---

def test_execute_passes_julie_result_and_returns_selina_result():
    executor = RecordingExecutor(result={"content": "key: value"})
    selina = Selina(executor)

    julie_result = _make_julie_result()
    result = selina.execute(julie_result)

    assert isinstance(result, SelinaResult)
    assert result.success is True
    assert result.expanded_task == "Read and return the contents of config.yaml"
    assert result.action == "read_file"
    assert result.result == {"content": "key: value"}
    assert result.error is None


def test_execute_builds_arguments_from_julie_result():
    executor = RecordingExecutor()
    selina = Selina(executor)

    julie_result = _make_julie_result(
        user_request="list my files",
        expanded_task="List all files in the home directory",
        plan=["list_directory"],
        uncertainty=[],
    )
    selina.execute(julie_result)

    assert len(executor.calls) == 1
    call = executor.calls[0]
    assert call["action"] == "list_directory"
    assert call["arguments"]["expanded_task"] == "List all files in the home directory"
    assert call["arguments"]["plan"] == ["list_directory"]
    assert call["arguments"]["uncertainty"] == []
    assert call["arguments"]["user_request"] == "list my files"


def test_execute_determines_action_from_first_step():
    executor = RecordingExecutor()
    selina = Selina(executor)

    julie_result = _make_julie_result(
        plan=["create_folder", "write_file", "verify"]
    )
    result = selina.execute(julie_result)

    assert result.action == "create_folder"


def test_execute_interpretation_contains_task_and_steps():
    executor = RecordingExecutor()
    selina = Selina(executor)

    julie_result = _make_julie_result(
        expanded_task="Deploy the app",
        plan=["build", "push", "restart"],
    )
    result = selina.execute(julie_result)

    assert "Deploy the app" in result.interpretation
    assert "build" in result.interpretation
    assert "push" in result.interpretation


# --- failure cases ---

def test_execute_returns_error_when_input_not_julie_result():
    executor = RecordingExecutor()
    selina = Selina(executor)

    with pytest.raises(TypeError, match="JulieResult"):
        selina.execute("not a julie result")


def test_execute_returns_error_when_expanded_task_empty():
    executor = RecordingExecutor()
    selina = Selina(executor)

    julie_result = _make_julie_result(expanded_task="   ")
    result = selina.execute(julie_result)

    assert result.success is False
    assert "empty" in result.error.lower()


def test_execute_returns_error_when_plan_empty():
    executor = RecordingExecutor()
    selina = Selina(executor)

    julie_result = _make_julie_result(plan=[])
    result = selina.execute(julie_result)

    assert result.success is False
    assert "action" in result.error.lower()


def test_execute_returns_error_when_executor_raises():
    executor = RaisingExecutor()
    selina = Selina(executor)

    julie_result = _make_julie_result()
    result = selina.execute(julie_result)

    assert result.success is False
    assert "Executor failed" in result.error


def test_execute_with_no_uncertainty():
    executor = RecordingExecutor(result="ok")
    selina = Selina(executor)

    julie_result = _make_julie_result(uncertainty=[])
    result = selina.execute(julie_result)

    assert result.success is True
    assert result.result == "ok"
