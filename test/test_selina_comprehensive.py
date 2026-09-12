"""Comprehensive tests for Selina covering all edge cases."""

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

    def __init__(self, exception=None):
        self.exception = exception or RuntimeError("Executor failed on purpose")

    def execute(self, action, arguments):
        raise self.exception


class SlowExecutor:
    """Fake executor that returns None (simulating a void operation)."""

    def execute(self, action, arguments):
        return None


class WeirdExecutor:
    """Fake executor that returns unexpected types."""

    def __init__(self, weird_result):
        self.weird_result = weird_result

    def execute(self, action, arguments):
        return self.weird_result


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


# === A. Valid JulieResult ===

def test_execute_accepts_julie_result():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result()
    result = selina.execute(julie_result)
    assert isinstance(result, SelinaResult)


def test_interpretation_is_generated():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(
        expanded_task="Deploy the app",
        plan=["build", "push"],
    )
    result = selina.execute(julie_result)
    assert "Deploy the app" in result.interpretation
    assert "build" in result.interpretation
    assert "push" in result.interpretation


def test_action_is_generated():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(plan=["read_file", "parse_yaml"])
    result = selina.execute(julie_result)
    assert result.action == "read_file"


def test_executor_receives_correct_action():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(plan=["write_file", "verify"])
    selina.execute(julie_result)
    assert executor.calls[0]["action"] == "write_file"


def test_executor_receives_correct_arguments():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(
        user_request="test request",
        expanded_task="test task",
        plan=["step_one"],
        uncertainty=["uncertain thing"],
    )
    selina.execute(julie_result)
    args = executor.calls[0]["arguments"]
    assert args["user_request"] == "test request"
    assert args["expanded_task"] == "test task"
    assert args["plan"] == ["step_one"]
    assert args["uncertainty"] == ["uncertain thing"]


def test_result_stored_correctly():
    executor = RecordingExecutor(result={"key": "value"})
    selina = Selina(executor)
    julie_result = _make_julie_result()
    result = selina.execute(julie_result)
    assert result.result == {"key": "value"}
    assert result.success is True


# === B. Invalid input types ===

def test_none_raises_type_error():
    executor = RecordingExecutor()
    selina = Selina(executor)
    with pytest.raises(TypeError, match="JulieResult"):
        selina.execute(None)


def test_string_raises_type_error():
    executor = RecordingExecutor()
    selina = Selina(executor)
    with pytest.raises(TypeError, match="JulieResult"):
        selina.execute("not a julie result")


def test_dict_raises_type_error():
    executor = RecordingExecutor()
    selina = Selina(executor)
    with pytest.raises(TypeError, match="JulieResult"):
        selina.execute({"expanded_task": "task"})


def test_unrelated_object_raises_type_error():
    executor = RecordingExecutor()
    selina = Selina(executor)
    with pytest.raises(TypeError, match="JulieResult"):
        selina.execute(42)


def test_list_raises_type_error():
    executor = RecordingExecutor()
    selina = Selina(executor)
    with pytest.raises(TypeError, match="JulieResult"):
        selina.execute([_make_julie_result()])


# === C. Empty expanded_task ===

def test_empty_expanded_task_returns_failure():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(expanded_task="")
    result = selina.execute(julie_result)
    assert result.success is False
    assert "empty" in result.error.lower()
    assert executor.calls == []


def test_whitespace_expanded_task_returns_failure():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(expanded_task="   \n\t  ")
    result = selina.execute(julie_result)
    assert result.success is False
    assert "empty" in result.error.lower()


# === D. Empty plan ===

def test_empty_plan_returns_failure():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(plan=[])
    result = selina.execute(julie_result)
    assert result.success is False
    assert "action" in result.error.lower()
    assert executor.calls == []


# === E. Multiple plan steps ===

def test_action_from_first_step():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(plan=["first_step", "second_step", "third_step"])
    result = selina.execute(julie_result)
    assert result.action == "first_step"


def test_all_plan_steps_in_arguments():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(plan=["step_a", "step_b", "step_c"])
    selina.execute(julie_result)
    assert executor.calls[0]["arguments"]["plan"] == ["step_a", "step_b", "step_c"]


# === F. Uncertainty propagation ===

def test_uncertainty_passed_to_executor():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(uncertainty=["unclear", "ambiguous"])
    selina.execute(julie_result)
    assert executor.calls[0]["arguments"]["uncertainty"] == ["unclear", "ambiguous"]


def test_empty_uncertainty_passed():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(uncertainty=[])
    selina.execute(julie_result)
    assert executor.calls[0]["arguments"]["uncertainty"] == []


# === G. Executor success ===

def test_success_result_has_all_fields():
    executor = RecordingExecutor(result="completed")
    selina = Selina(executor)
    julie_result = _make_julie_result()
    result = selina.execute(julie_result)
    assert result.success is True
    assert result.expanded_task == "Read and return the contents of config.yaml"
    assert result.interpretation != ""
    assert result.action == "read_file"
    assert result.result == "completed"
    assert result.error is None


# === H. Executor failure ===

def test_executor_exception_returns_failure():
    executor = RaisingExecutor(RuntimeError("boom"))
    selina = Selina(executor)
    julie_result = _make_julie_result()
    result = selina.execute(julie_result)
    assert result.success is False
    assert "boom" in result.error
    assert result.action == "read_file"


def test_executor_exception_preserves_interpretation():
    executor = RaisingExecutor(RuntimeError("boom"))
    selina = Selina(executor)
    julie_result = _make_julie_result(
        expanded_task="Do something",
        plan=["step_one"],
    )
    result = selina.execute(julie_result)
    assert "Do something" in result.interpretation


def test_type_error_from_executor_returns_failure():
    executor = RaisingExecutor(TypeError("bad type"))
    selina = Selina(executor)
    julie_result = _make_julie_result()
    result = selina.execute(julie_result)
    assert result.success is False
    assert "bad type" in result.error


# === I. Data loss checks ===

def test_user_request_not_lost():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(user_request="specific request text")
    selina.execute(julie_result)
    assert executor.calls[0]["arguments"]["user_request"] == "specific request text"


def test_expanded_task_not_lost():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(expanded_task="specific task text")
    result = selina.execute(julie_result)
    assert result.expanded_task == "specific task text"
    assert executor.calls[0]["arguments"]["expanded_task"] == "specific task text"


def test_plan_not_lost():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(plan=["a", "b", "c"])
    selina.execute(julie_result)
    assert executor.calls[0]["arguments"]["plan"] == ["a", "b", "c"]


def test_interpretation_not_lost():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(
        expanded_task="Test task",
        plan=["step_one"],
    )
    result = selina.execute(julie_result)
    assert "Test task" in result.interpretation
    assert "step_one" in result.interpretation


def test_error_preserved_on_executor_failure():
    executor = RaisingExecutor(RuntimeError("specific error message"))
    selina = Selina(executor)
    julie_result = _make_julie_result()
    result = selina.execute(julie_result)
    assert result.error == "specific error message"


# === Action normalization ===

def test_action_normalized_lowercase():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(plan=["Read File"])
    result = selina.execute(julie_result)
    assert result.action == "read_file"


def test_action_normalized_spaces_to_underscores():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(plan=["Create New Folder"])
    result = selina.execute(julie_result)
    assert result.action == "create_new_folder"


def test_action_stripped_whitespace():
    executor = RecordingExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result(plan=["  read_file  "])
    result = selina.execute(julie_result)
    assert result.action == "read_file"


# === Weird executor results ===

def test_executor_returns_none():
    executor = SlowExecutor()
    selina = Selina(executor)
    julie_result = _make_julie_result()
    result = selina.execute(julie_result)
    assert result.success is True
    assert result.result is None


def test_executor_returns_empty_string():
    executor = RecordingExecutor(result="")
    selina = Selina(executor)
    julie_result = _make_julie_result()
    result = selina.execute(julie_result)
    assert result.success is True
    assert result.result == ""


def test_executor_returns_large_dict():
    big_dict = {f"key_{i}": f"value_{i}" for i in range(100)}
    executor = RecordingExecutor(result=big_dict)
    selina = Selina(executor)
    julie_result = _make_julie_result()
    result = selina.execute(julie_result)
    assert result.success is True
    assert result.result == big_dict
