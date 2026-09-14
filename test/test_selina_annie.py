"""Tests for the AnnieResult -> Selina handoff."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from agent.annie.annie import AnnieResult
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

    def __init__(self, exception=None):
        self.exception = exception or RuntimeError("Executor failed on purpose")

    def execute(self, action, arguments):
        raise self.exception


def _make_annie_result(**overrides) -> AnnieResult:
    defaults = {
        "user_request": "Organize my Downloads folder",
        "interpretation": "The user wants Downloads organized into categories.",
        "requirements": [
            "Inspect the current Downloads contents",
            "Categorize files by type",
            "Move files into appropriate folders",
        ],
        "constraints": [
            "Do not invent a folder structure without evidence",
            "Inspect before modifying files",
        ],
        "technical_handoff": (
            "Selina should inspect the Downloads folder first, "
            "then determine a safe organization strategy."
        ),
        "clarification_needed": [
            "Preferred folder structure is not specified.",
        ],
        "raw_response": "{}",
    }
    defaults.update(overrides)
    return AnnieResult(**defaults)


# === A. Valid AnnieResult ===

def test_execute_from_annie_returns_selina_result():
    executor = RecordingExecutor(result={"files": ["a.pdf", "b.jpg"]})
    selina = Selina(executor)
    annie_result = _make_annie_result()

    result = selina.execute_from_annie(annie_result)

    assert isinstance(result, SelinaResult)
    assert result.success is True


def test_execute_from_annie_uses_technical_handoff_as_task():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(
        technical_handoff="Read the config file and return its contents."
    )

    result = selina.execute_from_annie(annie_result)

    assert result.expanded_task == "Read the config file and return its contents."


def test_execute_from_annie_uses_interpretation_directly():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(
        interpretation="The user wants a specific file read."
    )

    result = selina.execute_from_annie(annie_result)

    assert result.interpretation == "The user wants a specific file read."


def test_execute_from_annie_action_from_first_requirement():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(
        requirements=["Read the config file", "Parse the YAML"]
    )

    result = selina.execute_from_annie(annie_result)

    assert result.action == "read_the_config_file"


def test_execute_from_annie_explicit_action_overrides():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(
        requirements=["Inspect files", "Categorize them"]
    )

    result = selina.execute_from_annie(annie_result, action="list_directory")

    assert result.action == "list_directory"


def test_execute_from_annie_arguments_contain_all_annie_fields():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(
        user_request="my request",
        interpretation="my interpretation",
        requirements=["req1", "req2"],
        constraints=["con1"],
        technical_handoff="my handoff",
        clarification_needed=["clar1"],
    )

    selina.execute_from_annie(annie_result)

    args = executor.calls[0]["arguments"]
    assert args["user_request"] == "my request"
    assert args["interpretation"] == "my interpretation"
    assert args["requirements"] == ["req1", "req2"]
    assert args["constraints"] == ["con1"]
    assert args["technical_handoff"] == "my handoff"
    assert args["clarification_needed"] == ["clar1"]


def test_execute_from_annie_preserves_result():
    executor = RecordingExecutor(result={"key": "value"})
    selina = Selina(executor)
    annie_result = _make_annie_result()

    result = selina.execute_from_annie(annie_result)

    assert result.result == {"key": "value"}


# === B. Invalid input types ===

def test_execute_from_annie_rejects_non_annie_result():
    executor = RecordingExecutor()
    selina = Selina(executor)

    with pytest.raises(TypeError, match="AnnieResult"):
        selina.execute_from_annie("not an annie result")


def test_execute_from_annie_rejects_none():
    executor = RecordingExecutor()
    selina = Selina(executor)

    with pytest.raises(TypeError, match="AnnieResult"):
        selina.execute_from_annie(None)


def test_execute_from_annie_rejects_julie_result():
    """JulieResult should not be accepted by execute_from_annie."""
    from agent.julie.julie import JulieResult

    executor = RecordingExecutor()
    selina = Selina(executor)

    julie_result = JulieResult(
        user_request="test",
        context=None,
        expanded_task="task",
        plan=["step"],
        uncertainty=[],
        raw_response="{}",
    )

    with pytest.raises(TypeError, match="AnnieResult"):
        selina.execute_from_annie(julie_result)


# === C. Empty technical_handoff ===

def test_execute_from_annie_empty_handoff_returns_failure():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(technical_handoff="")

    result = selina.execute_from_annie(annie_result)

    assert result.success is False
    assert "empty" in result.error.lower()
    assert executor.calls == []


def test_execute_from_annie_whitespace_handoff_returns_failure():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(technical_handoff="   \n\t  ")

    result = selina.execute_from_annie(annie_result)

    assert result.success is False
    assert "empty" in result.error.lower()


# === D. Empty requirements ===

def test_execute_from_annie_empty_requirements_returns_failure():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(requirements=[])

    result = selina.execute_from_annie(annie_result)

    assert result.success is False
    assert "action" in result.error.lower()
    assert executor.calls == []


# === E. Explicit action parameter ===

def test_execute_from_annie_explicit_action_used_directly():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result()

    result = selina.execute_from_annie(annie_result, action="custom_action")

    assert result.action == "custom_action"
    assert executor.calls[0]["action"] == "custom_action"


def test_execute_from_annie_none_action_derives_from_requirements():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(
        requirements=["Create new folder", "Move files"]
    )

    result = selina.execute_from_annie(annie_result, action=None)

    assert result.action == "create_new_folder"


# === F. Executor failure ===

def test_execute_from_annie_executor_failure_returns_error():
    executor = RaisingExecutor(RuntimeError("boom"))
    selina = Selina(executor)
    annie_result = _make_annie_result()

    result = selina.execute_from_annie(annie_result)

    assert result.success is False
    assert "boom" in result.error
    assert result.action  # action was determined before failure


def test_execute_from_annie_failure_preserves_interpretation():
    executor = RaisingExecutor(RuntimeError("boom"))
    selina = Selina(executor)
    annie_result = _make_annie_result(
        interpretation="Custom interpretation text"
    )

    result = selina.execute_from_annie(annie_result)

    assert result.interpretation == "Custom interpretation text"


# === G. Action normalization ===

def test_action_normalized_lowercase():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(requirements=["Read File"])

    result = selina.execute_from_annie(annie_result)

    assert result.action == "read_file"


def test_action_normalized_spaces_to_underscores():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(requirements=["Create New Folder"])

    result = selina.execute_from_annie(annie_result)

    assert result.action == "create_new_folder"


def test_action_stripped_whitespace():
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(requirements=["  read_file  "])

    result = selina.execute_from_annie(annie_result)

    assert result.action == "read_file"


# === H. Existing execute() still works ===

def test_original_execute_still_accepts_julie_result():
    """The original execute() method is untouched."""
    from agent.julie.julie import JulieResult

    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = JulieResult(
        user_request="test",
        context=None,
        expanded_task="task",
        plan=["step_one"],
        uncertainty=[],
        raw_response="{}",
    )

    result = selina.execute(julie_result)

    assert isinstance(result, SelinaResult)
    assert result.success is True
    assert result.action == "step_one"
