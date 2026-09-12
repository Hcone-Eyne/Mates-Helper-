"""Comprehensive tests for Julie covering all edge cases."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from agent.julie.julie import Julie, JulieResult, OllamaReasoningBackend


class RecordingBackend:
    def __init__(self, response):
        self.response = response
        self.messages = None

    def generate(self, messages):
        self.messages = messages
        return self.response


class RaisingBackend:
    def __init__(self, exception):
        self.exception = exception

    def generate(self, messages):
        raise self.exception


# === A. Valid user input ===

def test_valid_string_input():
    backend = RecordingBackend('{"expanded_task":"Do it","plan":["Step 1"],"uncertainty":[]}')
    julie = Julie(backend)
    result = julie.reason("do the thing")
    assert isinstance(result, JulieResult)
    assert result.user_request == "do the thing"
    assert result.expanded_task == "Do it"
    assert result.plan == ["Step 1"]
    assert result.uncertainty == []


def test_backend_called_with_correct_messages():
    backend = RecordingBackend('{"expanded_task":"Task","plan":[],"uncertainty":[]}')
    julie = Julie(backend)
    julie.reason("test input")
    # Should have system prompt + user message
    assert len(backend.messages) == 2
    assert backend.messages[0]["role"] == "system"
    assert backend.messages[1] == {"role": "user", "content": "test input"}


def test_julie_result_is_frozen():
    backend = RecordingBackend('{"expanded_task":"Task","plan":[],"uncertainty":[]}')
    julie = Julie(backend)
    result = julie.reason("test")
    with pytest.raises(AttributeError):
        result.user_request = "changed"


# === B. Empty input ===

def test_empty_string_returns_empty_string():
    backend = RecordingBackend("should not be called")
    julie = Julie(backend)
    result = julie.reason("")
    assert result == ""


def test_whitespace_only_returns_empty_string():
    backend = RecordingBackend("should not be called")
    julie = Julie(backend)
    result = julie.reason("   \n\t  ")
    assert result == ""


# === C. Invalid input types ===

def test_none_input_raises_type_error():
    backend = RecordingBackend("should not be called")
    julie = Julie(backend)
    with pytest.raises(TypeError, match="string"):
        julie.reason(None)


def test_integer_input_raises_type_error():
    backend = RecordingBackend("should not be called")
    julie = Julie(backend)
    with pytest.raises(TypeError, match="string"):
        julie.reason(42)


def test_list_input_raises_type_error():
    backend = RecordingBackend("should not be called")
    julie = Julie(backend)
    with pytest.raises(TypeError, match="string"):
        julie.reason(["item"])


def test_dict_input_raises_type_error():
    backend = RecordingBackend("should not be called")
    julie = Julie(backend)
    with pytest.raises(TypeError, match="string"):
        julie.reason({"key": "value"})


def test_bool_input_raises_type_error():
    backend = RecordingBackend("should not be called")
    julie = Julie(backend)
    with pytest.raises(TypeError, match="string"):
        julie.reason(True)


# === D. Context handling ===

def test_context_none_not_sent_to_backend():
    backend = RecordingBackend('{"expanded_task":"Task","plan":[],"uncertainty":[]}')
    julie = Julie(backend)
    julie.reason("do it", None)
    # Only system + user, no context message
    assert len(backend.messages) == 2
    assert backend.messages[0]["role"] == "system"
    assert backend.messages[1]["role"] == "user"


def test_valid_context_passed_to_backend():
    backend = RecordingBackend('{"expanded_task":"Task","plan":[],"uncertainty":[]}')
    julie = Julie(backend)
    julie.reason("do it", "some context here")
    # system + context + user
    assert len(backend.messages) == 3
    assert backend.messages[0]["role"] == "system"
    assert backend.messages[1]["role"] == "system"
    assert "Context:\nsome context here" == backend.messages[1]["content"]
    assert backend.messages[2] == {"role": "user", "content": "do it"}


def test_context_is_stripped():
    backend = RecordingBackend('{"expanded_task":"Task","plan":[],"uncertainty":[]}')
    julie = Julie(backend)
    result = julie.reason("do it", "  padded context  ")
    assert result.context == "padded context"


def test_invalid_context_type_raises():
    backend = RecordingBackend("should not be called")
    julie = Julie(backend)
    with pytest.raises(TypeError, match="Context"):
        julie.reason("do it", 123)


def test_context_stored_in_result():
    backend = RecordingBackend('{"expanded_task":"Task","plan":[],"uncertainty":[]}')
    julie = Julie(backend)
    result = julie.reason("do it", "my context")
    assert result.context == "my context"


# === E. JSON parsing ===

def test_valid_json():
    backend = RecordingBackend('{"expanded_task":"Deploy app","plan":["Build","Push"],"uncertainty":["Need keys"]}')
    julie = Julie(backend)
    result = julie.reason("deploy")
    assert result.expanded_task == "Deploy app"
    assert result.plan == ["Build", "Push"]
    assert result.uncertainty == ["Need keys"]


def test_json_in_markdown_fences():
    json_str = '```json\n{"expanded_task":"Task","plan":["Step"],"uncertainty":[]}\n```'
    backend = RecordingBackend(json_str)
    julie = Julie(backend)
    result = julie.reason("do it")
    assert result.expanded_task == "Task"


def test_json_in_markdown_fences_without_json_label():
    json_str = '```\n{"expanded_task":"Task","plan":["Step"],"uncertainty":[]}\n```'
    backend = RecordingBackend(json_str)
    julie = Julie(backend)
    result = julie.reason("do it")
    assert result.expanded_task == "Task"


def test_missing_expanded_task_raises():
    backend = RecordingBackend('{"plan":["Step"],"uncertainty":[]}')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="missing a required field"):
        julie.reason("do it")


def test_missing_plan_raises():
    backend = RecordingBackend('{"expanded_task":"Task","uncertainty":[]}')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="missing a required field"):
        julie.reason("do it")


def test_missing_uncertainty_raises():
    backend = RecordingBackend('{"expanded_task":"Task","plan":["Step"]}')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="missing a required field"):
        julie.reason("do it")


def test_unknown_fields_raises():
    backend = RecordingBackend('{"expanded_task":"Task","plan":[],"uncertainty":[],"extra":"bad"}')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="unknown fields"):
        julie.reason("do it")


def test_invalid_json_syntax_raises():
    backend = RecordingBackend("not json at all")
    julie = Julie(backend)
    with pytest.raises(ValueError, match="invalid JSON"):
        julie.reason("do it")


def test_non_object_json_raises():
    backend = RecordingBackend('"just a string"')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="must be an object"):
        julie.reason("do it")


def test_array_json_raises():
    backend = RecordingBackend('[1, 2, 3]')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="must be an object"):
        julie.reason("do it")


def test_empty_expanded_task_in_json_raises():
    backend = RecordingBackend('{"expanded_task":"","plan":[],"uncertainty":[]}')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="invalid field types"):
        julie.reason("do it")


def test_empty_plan_step_in_json_raises():
    backend = RecordingBackend('{"expanded_task":"Task","plan":[""],"uncertainty":[]}')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="invalid field types"):
        julie.reason("do it")


def test_non_string_expanded_task_raises():
    backend = RecordingBackend('{"expanded_task":123,"plan":[],"uncertainty":[]}')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="invalid field types"):
        julie.reason("do it")


def test_non_list_plan_raises():
    backend = RecordingBackend('{"expanded_task":"Task","plan":"step","uncertainty":[]}')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="invalid field types"):
        julie.reason("do it")


def test_non_list_uncertainty_raises():
    backend = RecordingBackend('{"expanded_task":"Task","plan":[],"uncertainty":"yes"}')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="invalid field types"):
        julie.reason("do it")


def test_uncertainty_items_must_be_strings():
    backend = RecordingBackend('{"expanded_task":"Task","plan":["Step"],"uncertainty":[123]}')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="invalid field types"):
        julie.reason("do it")


def test_plan_items_must_be_strings():
    backend = RecordingBackend('{"expanded_task":"Task","plan":[123],"uncertainty":[]}')
    julie = Julie(backend)
    with pytest.raises(ValueError, match="invalid field types"):
        julie.reason("do it")


# === F. Backend failures ===

def test_backend_raises_exception():
    backend = RaisingBackend(RuntimeError("backend exploded"))
    julie = Julie(backend)
    with pytest.raises(RuntimeError, match="backend exploded"):
        julie.reason("do it")


def test_backend_returns_non_string_raises_type_error():
    class BadBackend:
        def generate(self, messages):
            return 42

    julie = Julie(BadBackend())
    with pytest.raises(TypeError, match="must return a string"):
        julie.reason("do it")


def test_backend_returns_none_raises_type_error():
    class BadBackend:
        def generate(self, messages):
            return None

    julie = Julie(BadBackend())
    with pytest.raises(TypeError, match="must return a string"):
        julie.reason("do it")


def test_backend_returns_dict_raises_type_error():
    class BadBackend:
        def generate(self, messages):
            return {"key": "value"}

    julie = Julie(BadBackend())
    with pytest.raises(TypeError, match="must return a string"):
        julie.reason("do it")


# === Data preservation ===

def test_raw_response_stored():
    raw = '{"expanded_task":"Task","plan":[],"uncertainty":[]}'
    backend = RecordingBackend(raw)
    julie = Julie(backend)
    result = julie.reason("do it")
    assert result.raw_response == raw


def test_user_request_stripped():
    backend = RecordingBackend('{"expanded_task":"Task","plan":[],"uncertainty":[]}')
    julie = Julie(backend)
    result = julie.reason("  do it  ")
    assert result.user_request == "do it"
