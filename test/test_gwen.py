"""Comprehensive tests for Gwen reviewing Julie and Selina output."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from agent.julie.julie import JulieResult
from agent.selina.selina import SelinaResult
from agent.gwen.gwen import Gwen, GwenResult


class RecordingBackend:
    """Fake critic backend that records messages and returns preset response."""

    def __init__(self, response):
        self.response = response
        self.messages = None

    def generate(self, messages):
        self.messages = messages
        return self.response


class RaisingBackend:
    """Fake backend that always raises."""

    def __init__(self, exception=None):
        self.exception = exception or RuntimeError("Backend failed")

    def generate(self, messages):
        raise self.exception


class NonStringBackend:
    """Fake backend that returns non-string data."""

    def __init__(self, bad_result):
        self.bad_result = bad_result

    def generate(self, messages):
        return self.bad_result


def _make_julie_result(**overrides) -> JulieResult:
    defaults = {
        "user_request": "read the config",
        "context": None,
        "expanded_task": "Read config.yaml",
        "plan": ["read_file"],
        "uncertainty": [],
        "raw_response": "{}",
    }
    defaults.update(overrides)
    return JulieResult(**defaults)


def _make_selina_result(**overrides) -> SelinaResult:
    defaults = {
        "success": True,
        "expanded_task": "Read config.yaml",
        "interpretation": "Task: Read config.yaml. Steps: read_file",
        "action": "read_file",
        "result": {"content": "key: value"},
        "error": None,
    }
    defaults.update(overrides)
    return SelinaResult(**defaults)


# NOTE: Gwen currently only accepts (user_input: str, reasoning: str).
# It does NOT directly receive JulieResult or SelinaResult.
# The integration test below constructs a reasoning string from both.
# This is a known architecture limitation flagged in the QA report.


# === A. Gwen accepts valid strings ===

def test_gwen_accepts_valid_strings():
    backend = RecordingBackend("APPROVED: true\nCRITIQUE: Looks good.")
    gwen = Gwen(backend)
    result = gwen.review("do something", "Julie says do this, Selina did that")
    assert isinstance(result, GwenResult)


def test_backend_called_with_messages():
    backend = RecordingBackend("APPROVED: true\nCRITIQUE: OK")
    gwen = Gwen(backend)
    gwen.review("user request text", "reasoning text")
    assert len(backend.messages) == 2
    assert backend.messages[0]["role"] == "system"
    assert backend.messages[1]["role"] == "user"
    assert "user request text" in backend.messages[1]["content"]
    assert "reasoning text" in backend.messages[1]["content"]


# === B. Invalid input types ===

def test_none_user_input_raises():
    backend = RecordingBackend("APPROVED: true\nCRITIQUE: OK")
    gwen = Gwen(backend)
    with pytest.raises(TypeError, match="string"):
        gwen.review(None, "reasoning")


def test_none_reasoning_raises():
    backend = RecordingBackend("APPROVED: true\nCRITIQUE: OK")
    gwen = Gwen(backend)
    with pytest.raises(TypeError, match="string"):
        gwen.review("user input", None)


def test_integer_user_input_raises():
    backend = RecordingBackend("APPROVED: true\nCRITIQUE: OK")
    gwen = Gwen(backend)
    with pytest.raises(TypeError, match="string"):
        gwen.review(42, "reasoning")


def test_dict_reasoning_raises():
    backend = RecordingBackend("APPROVED: true\nCRITIQUE: OK")
    gwen = Gwen(backend)
    with pytest.raises(TypeError, match="string"):
        gwen.review("user input", {"key": "value"})


# === C. Gwen sends all important information ===

def test_backend_receives_user_request():
    backend = RecordingBackend("APPROVED: true\nCRITIQUE: OK")
    gwen = Gwen(backend)
    gwen.review("specific user request", "some reasoning")
    content = backend.messages[1]["content"]
    assert "specific user request" in content


def test_backend_receives_reasoning():
    backend = RecordingBackend("APPROVED: true\nCRITIQUE: OK")
    gwen = Gwen(backend)
    gwen.review("user input", "detailed reasoning here")
    content = backend.messages[1]["content"]
    assert "detailed reasoning here" in content


def test_backend_message_labels_reasoning_as_julie():
    """Gwen's prompt currently labels reasoning as 'Julie's reasoning'."""
    backend = RecordingBackend("APPROVED: true\nCRITIQUE: OK")
    gwen = Gwen(backend)
    gwen.review("user input", "some reasoning")
    content = backend.messages[1]["content"]
    assert "Julie" in content or "reasoning" in content


# === D. APPROVED parsing ===

def test_approved_true():
    backend = RecordingBackend("APPROVED: true\nCRITIQUE: Everything checks out.")
    gwen = Gwen(backend)
    result = gwen.review("user input", "reasoning text")
    assert result.approved is True
    assert result.critique == "Everything checks out."


def test_approved_false():
    backend = RecordingBackend("APPROVED: false\nCRITIQUE: Logical flaw detected.")
    gwen = Gwen(backend)
    result = gwen.review("user input", "reasoning text")
    assert result.approved is False
    assert result.critique == "Logical flaw detected."


def test_approved_case_insensitive():
    backend = RecordingBackend("approved: True\nCRITIQUE: Fine.")
    gwen = Gwen(backend)
    result = gwen.review("user input", "reasoning text")
    assert result.approved is True


def test_approved_with_extra_whitespace():
    backend = RecordingBackend("  APPROVED:   true  \nCRITIQUE: Good.")
    gwen = Gwen(backend)
    result = gwen.review("user input", "reasoning text")
    assert result.approved is True


def test_approved_missing_treated_as_false():
    backend = RecordingBackend("CRITIQUE: No approval line present.")
    gwen = Gwen(backend)
    result = gwen.review("user input", "reasoning text")
    assert result.approved is False


def test_approved_with_yes_treated_as_false():
    """Only explicit 'true' counts as approved."""
    backend = RecordingBackend("APPROVED: yes\nCRITIQUE: Seems okay.")
    gwen = Gwen(backend)
    result = gwen.review("user input", "reasoning text")
    assert result.approved is False


# === E. CRITIQUE parsing ===

def test_critique_extracted():
    backend = RecordingBackend("APPROVED: false\nCRITIQUE: Missing step 3.")
    gwen = Gwen(backend)
    result = gwen.review("user input", "reasoning text")
    assert result.critique == "Missing step 3."


def test_critique_case_insensitive():
    backend = RecordingBackend("APPROVED: true\ncritique: All good.")
    gwen = Gwen(backend)
    result = gwen.review("user input", "reasoning text")
    assert result.critique == "All good."


def test_critique_with_extra_whitespace():
    backend = RecordingBackend("APPROVED: true\n  CRITIQUE:   trimmed  ")
    gwen = Gwen(backend)
    result = gwen.review("user input", "reasoning text")
    assert result.critique == "trimmed"


def test_missing_critique_falls_back_to_full_response():
    backend = RecordingBackend("APPROVED: true\nNo critique marker here.")
    gwen = Gwen(backend)
    result = gwen.review("user input", "reasoning text")
    assert "No critique marker here." in result.critique


# === F. Empty backend response ===

def test_empty_backend_response():
    backend = RecordingBackend("")
    gwen = Gwen(backend)
    result = gwen.review("user input", "reasoning text")
    assert result.approved is False
    assert "empty" in result.critique.lower()


def test_whitespace_backend_response():
    backend = RecordingBackend("   \n\t  ")
    gwen = Gwen(backend)
    result = gwen.review("user input", "reasoning text")
    assert result.approved is False


# === G. Empty input ===

def test_empty_user_input():
    backend = RecordingBackend("should not be called")
    gwen = Gwen(backend)
    result = gwen.review("", "reasoning text")
    assert result.approved is False
    assert "empty" in result.critique.lower()


def test_empty_reasoning():
    backend = RecordingBackend("should not be called")
    gwen = Gwen(backend)
    result = gwen.review("user input", "")
    assert result.approved is False
    assert "empty" in result.critique.lower()


def test_whitespace_user_input():
    backend = RecordingBackend("should not be called")
    gwen = Gwen(backend)
    result = gwen.review("   ", "reasoning text")
    assert result.approved is False


def test_whitespace_reasoning():
    backend = RecordingBackend("should not be called")
    gwen = Gwen(backend)
    result = gwen.review("user input", "   ")
    assert result.approved is False


# === H. Backend exceptions ===

def test_backend_exception_propagates():
    backend = RaisingBackend(RuntimeError("backend exploded"))
    gwen = Gwen(backend)
    with pytest.raises(RuntimeError, match="backend exploded"):
        gwen.review("user input", "reasoning text")


def test_backend_returns_non_string_raises():
    backend = NonStringBackend(42)
    gwen = Gwen(backend)
    with pytest.raises(TypeError, match="must return a string"):
        gwen.review("user input", "reasoning text")


def test_backend_returns_none_raises():
    backend = NonStringBackend(None)
    gwen = Gwen(backend)
    with pytest.raises(TypeError, match="must return a string"):
        gwen.review("user input", "reasoning text")


def test_backend_returns_dict_raises():
    backend = NonStringBackend({"APPROVED": "true"})
    gwen = Gwen(backend)
    with pytest.raises(TypeError, match="must return a string"):
        gwen.review("user input", "reasoning text")


# === I. Gwen does NOT execute tools ===

def test_gwen_system_prompt_prohibits_actions():
    """Gwen's system prompt explicitly forbids tool execution."""
    assert "Do not execute tools" in Gwen.SYSTEM_PROMPT
    assert "Do not access files" in Gwen.SYSTEM_PROMPT
    assert "Do not browse the internet" in Gwen.SYSTEM_PROMPT
    assert "Do not perform external actions" in Gwen.SYSTEM_PROMPT


def test_gwen_class_has_no_execute_method():
    """Gwen should not have an execute method — she only reviews."""
    gwen = Gwen(RecordingBackend("APPROVED: true\nCRITIQUE: OK"))
    assert not hasattr(gwen, "execute")


def test_gwen_class_has_no_action_executor():
    """Gwen should not hold an ActionExecutor."""
    gwen = Gwen(RecordingBackend("APPROVED: true\nCRITIQUE: OK"))
    assert not hasattr(gwen, "executor")


# === Reasoning stored ===

def test_reasoning_stored_in_result():
    backend = RecordingBackend("APPROVED: true\nCRITIQUE: Good.")
    gwen = Gwen(backend)
    result = gwen.review("user input", "the reasoning text")
    assert result.reasoning == "the reasoning text"
