"""Tests for the AnnieResult -> Selina handoff."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from agent.annie.annie import AnnieResult
from agent.selina.selina import Selina, SelinaResult, _resolve_action, SUPPORTED_ACTIONS


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
        requirements=["List all folder names", "Categorize them"]
    )

    result = selina.execute_from_annie(annie_result)

    assert result.action == "list_directory"


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
        requirements=["List all files", "Sort by type"],
        constraints=["con1"],
        technical_handoff="my handoff",
        clarification_needed=["clar1"],
    )

    selina.execute_from_annie(annie_result)

    args = executor.calls[0]["arguments"]
    assert args["user_request"] == "my request"
    assert args["interpretation"] == "my interpretation"
    assert args["requirements"] == ["List all files", "Sort by type"]
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
        requirements=["Sort files by type", "Create new folder"]
    )

    result = selina.execute_from_annie(annie_result, action=None)

    assert result.action == "organise_folder"


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


# === G. Action resolution (keyword matching) ===

def test_action_resolves_list_keyword():
    """Requirements containing 'list' should resolve to list_directory."""
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(requirements=["List all files"])

    result = selina.execute_from_annie(annie_result)

    assert result.action == "list_directory"


def test_action_resolves_show_keyword():
    """Requirements containing 'show' should resolve to list_directory."""
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(requirements=["Show directory contents"])

    result = selina.execute_from_annie(annie_result)

    assert result.action == "list_directory"


def test_action_resolves_organise_keyword():
    """Requirements containing 'organise' should resolve to organise_folder."""
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(requirements=["Organise files by type"])

    result = selina.execute_from_annie(annie_result)

    assert result.action == "organise_folder"


def test_action_resolves_sort_keyword():
    """Requirements containing 'sort' should resolve to organise_folder."""
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(requirements=["Sort files into categories"])

    result = selina.execute_from_annie(annie_result)

    assert result.action == "organise_folder"


def test_action_unmatched_returns_empty():
    """Requirements with no supported keyword should return empty action."""
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(
        requirements=["Delete everything", "Format the disk"]
    )

    result = selina.execute_from_annie(annie_result)

    assert result.success is False
    assert "action" in result.error.lower()


def test_action_whole_word_matching():
    """Keyword must match as a whole word, not a substring."""
    # "display" should match, but "indisposed" should not trigger "display"
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(
        requirements=["I am indisposed today"]
    )

    result = selina.execute_from_annie(annie_result)

    # "display" is not a substring of "indisposed", so no match
    assert result.success is False


def test_action_case_insensitive():
    """Matching should be case-insensitive."""
    executor = RecordingExecutor()
    selina = Selina(executor)
    annie_result = _make_annie_result(requirements=["LIST all folders"])

    result = selina.execute_from_annie(annie_result)

    assert result.action == "list_directory"


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
        plan=["list all files"],
        uncertainty=[],
        raw_response="{}",
    )

    result = selina.execute(julie_result)

    assert isinstance(result, SelinaResult)
    assert result.success is True
    assert result.action == "list_directory"


# === I. _resolve_action unit tests ===

def test_resolve_action_empty_requirements():
    """Empty requirements list should return empty string."""
    assert _resolve_action([]) == ""


def test_resolve_action_no_match():
    """Requirements with no supported keyword should return empty string."""
    assert _resolve_action(["Delete everything", "Format the disk"]) == ""


def test_resolve_action_list_directory():
    """Requirements with 'list' should resolve to list_directory."""
    assert _resolve_action(["List all folder names"]) == "list_directory"


def test_resolve_action_organise_folder():
    """Requirements with 'sort' should resolve to organise_folder."""
    assert _resolve_action(["Sort files by type"]) == "organise_folder"


def test_resolve_action_first_match_wins():
    """The first matching requirement determines the action."""
    assert _resolve_action(
        ["Sort files", "List all folders"]
    ) == "organise_folder"


def test_resolve_action_scans_all_requirements():
    """Later requirements are checked if earlier ones don't match."""
    assert _resolve_action(
        ["Delete everything", "Show directory contents"]
    ) == "list_directory"


def test_resolve_action_supported_actions_complete():
    """All actions in SUPPORTED_ACTIONS should be resolvable."""
    for action_name, keywords in SUPPORTED_ACTIONS.items():
        for kw in keywords:
            result = _resolve_action([f"Please {kw} the files"])
            assert result == action_name, (
                f"Keyword '{kw}' should resolve to '{action_name}', got '{result}'"
            )
