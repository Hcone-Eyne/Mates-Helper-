"""Integration test: Julie -> Selina -> Gwen pipeline with fake backends."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from agent.julie.julie import Julie, JulieResult
from agent.selina.selina import Selina, SelinaResult
from agent.gwen.gwen import Gwen, GwenResult


# === Fake backends ===

class RecordingBackend:
    """Records messages and returns preset response."""

    def __init__(self, response):
        self.response = response
        self.messages = []

    def generate(self, messages):
        self.messages = messages
        return self.response


class RecordingExecutor:
    """Records calls and returns preset result."""

    def __init__(self, result="done"):
        self.result = result
        self.calls = []

    def execute(self, action, arguments):
        self.calls.append({"action": action, "arguments": arguments})
        return self.result


class RaisingExecutor:
    """Always raises an exception."""

    def execute(self, action, arguments):
        raise RuntimeError("Executor failed on purpose")


# === Helpers ===

def _build_reasoning_string(julie_result: JulieResult, selina_result: SelinaResult) -> str:
    """Build a reasoning string that combines Julie and Selina output for Gwen."""
    parts = [
        f"User request: {julie_result.user_request}",
        f"Expanded task: {julie_result.expanded_task}",
        f"Plan: {', '.join(julie_result.plan)}",
        f"Uncertainty: {', '.join(julie_result.uncertainty)}",
        "",
        f"Selina interpretation: {selina_result.interpretation}",
        f"Selina action: {selina_result.action}",
        f"Selina success: {selina_result.success}",
        f"Selina result: {selina_result.result}",
        f"Selina error: {selina_result.error}",
    ]
    return "\n".join(parts)


# === Integration tests ===

def test_full_pipeline_success():
    """Julie -> Selina -> Gwen with successful execution."""
    # 1. Julie
    julie_backend = RecordingBackend(
        '{"expanded_task":"Read config.yaml","plan":["read_file","parse"],"uncertainty":[]}'
    )
    julie = Julie(julie_backend)
    julie_result = julie.reason("read the config")

    # 2. Selina
    executor = RecordingExecutor(result={"key": "value"})
    selina = Selina(executor)
    selina_result = selina.execute(julie_result)

    # 3. Gwen
    reasoning = _build_reasoning_string(julie_result, selina_result)
    gwen_backend = RecordingBackend("APPROVED: true\nCRITIQUE: Execution matches the plan.")
    gwen = Gwen(gwen_backend)
    gwen_result = gwen.review(julie_result.user_request, reasoning)

    # Verify data flow
    assert isinstance(julie_result, JulieResult)
    assert isinstance(selina_result, SelinaResult)
    assert isinstance(gwen_result, GwenResult)

    # Julie produced correct output
    assert julie_result.expanded_task == "Read config.yaml"
    assert julie_result.plan == ["read_file", "parse"]

    # Selina executed correctly
    assert selina_result.success is True
    assert selina_result.action == "read_file"
    assert selina_result.result == {"key": "value"}

    # Gwen approved
    assert gwen_result.approved is True
    assert "matches the plan" in gwen_result.critique

    # Data not lost between agents
    assert executor.calls[0]["arguments"]["user_request"] == "read the config"
    assert executor.calls[0]["arguments"]["expanded_task"] == "Read config.yaml"


def test_full_pipeline_failure_at_selina():
    """Julie -> Selina (fails) -> Gwen rejects."""
    # 1. Julie
    julie_backend = RecordingBackend(
        '{"expanded_task":"Deploy app","plan":["deploy"],"uncertainty":["might fail"]}'
    )
    julie = Julie(julie_backend)
    julie_result = julie.reason("deploy the app")

    # 2. Selina with failing executor
    executor = RaisingExecutor()
    selina = Selina(executor)
    selina_result = selina.execute(julie_result)

    # 3. Gwen
    reasoning = _build_reasoning_string(julie_result, selina_result)
    gwen_backend = RecordingBackend(
        "APPROVED: false\nCRITIQUE: Selina failed to execute the action."
    )
    gwen = Gwen(gwen_backend)
    gwen_result = gwen.review(julie_result.user_request, reasoning)

    # Selina failed
    assert selina_result.success is False
    assert "failed" in selina_result.error.lower()

    # Gwen rejected because Selina failed
    assert gwen_result.approved is False


def test_full_pipeline_bad_reasoning():
    """Julie (bad plan) -> Selina -> Gwen rejects the reasoning."""
    # 1. Julie with questionable plan
    julie_backend = RecordingBackend(
        '{"expanded_task":"Delete everything","plan":["rm -rf /"],"uncertainty":["destructive"]}'
    )
    julie = Julie(julie_backend)
    julie_result = julie.reason("clean up files")

    # 2. Selina
    executor = RecordingExecutor(result="deleted")
    selina = Selina(executor)
    selina_result = selina.execute(julie_result)

    # 3. Gwen should catch the dangerous plan
    reasoning = _build_reasoning_string(julie_result, selina_result)
    gwen_backend = RecordingBackend(
        "APPROVED: false\nCRITIQUE: Dangerous command, should not proceed."
    )
    gwen = Gwen(gwen_backend)
    gwen_result = gwen.review(julie_result.user_request, reasoning)

    assert gwen_result.approved is False
    assert "dangerous" in gwen_result.critique.lower()


def test_data_not_lost_between_agents():
    """Verify all data fields survive the pipeline."""
    # 1. Julie
    julie_backend = RecordingBackend(
        '{"expanded_task":"Specific task text","plan":["step_a","step_b"],"uncertainty":["unclear part"]}'
    )
    julie = Julie(julie_backend)
    julie_result = julie.reason("specific user request", "some context")

    # 2. Selina
    executor = RecordingExecutor(result="result_value")
    selina = Selina(executor)
    selina_result = selina.execute(julie_result)

    # Check Selina preserved Julie's data
    assert selina_result.expanded_task == "Specific task text"
    assert executor.calls[0]["arguments"]["user_request"] == "specific user request"
    assert executor.calls[0]["arguments"]["plan"] == ["step_a", "step_b"]
    assert executor.calls[0]["arguments"]["uncertainty"] == ["unclear part"]

    # Check Selina added its own data
    assert selina_result.action == "step_a"
    assert selina_result.interpretation != ""
    assert selina_result.result == "result_value"

    # 3. Gwen
    reasoning = _build_reasoning_string(julie_result, selina_result)
    gwen_backend = RecordingBackend("APPROVED: true\nCRITIQUE: Good.")
    gwen = Gwen(gwen_backend)
    gwen_result = gwen.review(julie_result.user_request, reasoning)

    # Gwen received the combined reasoning
    assert "Specific task text" in gwen_backend.messages[1]["content"]
    assert "step_a" in gwen_backend.messages[1]["content"]
    assert "result_value" in gwen_backend.messages[1]["content"]


def test_gwen_receives_both_julie_and_selina_info():
    """Verify Gwen's backend receives information from both Julie and Selina."""
    julie_backend = RecordingBackend(
        '{"expanded_task":"Task","plan":["action"],"uncertainty":[]}'
    )
    julie = Julie(julie_backend)
    julie_result = julie.reason("do it")

    executor = RecordingExecutor(result="the_result")
    selina = Selina(executor)
    selina_result = selina.execute(julie_result)

    reasoning = _build_reasoning_string(julie_result, selina_result)
    gwen_backend = RecordingBackend("APPROVED: true\nCRITIQUE: OK")
    gwen = Gwen(gwen_backend)
    gwen.review("do it", reasoning)

    content = gwen_backend.messages[1]["content"]

    # Julie info present
    assert "Expanded task: Task" in content
    assert "Plan: action" in content

    # Selina info present
    assert "Selina action:" in content
    assert "Selina success: True" in content
    assert "Selina result: the_result" in content


def test_pipeline_works_with_context():
    """Full pipeline with Julie receiving context."""
    julie_backend = RecordingBackend(
        '{"expanded_task":"Use context","plan":["step"],"uncertainty":[]}'
    )
    julie = Julie(julie_backend)
    julie_result = julie.reason("do it", "important context")

    executor = RecordingExecutor(result="ok")
    selina = Selina(executor)
    selina_result = selina.execute(julie_result)

    reasoning = _build_reasoning_string(julie_result, selina_result)
    gwen_backend = RecordingBackend("APPROVED: true\nCRITIQUE: Good use of context.")
    gwen = Gwen(gwen_backend)
    gwen_result = gwen.review(julie_result.user_request, reasoning)

    assert julie_result.context == "important context"
    assert selina_result.success is True
    assert gwen_result.approved is True
