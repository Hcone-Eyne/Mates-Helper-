"""Tests for Julie's _parse_result and edge cases."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.julie.julie import Julie, JulieResult


class TestJulieParseResult:
    """Test Julie._parse_result static method."""

    def test_valid_json_response(self):
        raw = '{"expanded_task": "list files", "plan": ["step 1"], "uncertainty": []}'
        result = Julie._parse_result(raw)
        assert result["expanded_task"] == "list files"
        assert result["plan"] == ["step 1"]
        assert result["uncertainty"] == []

    def test_valid_json_with_whitespace(self):
        raw = '  \n  {"expanded_task": "task", "plan": ["a", "b"], "uncertainty": ["u"]}  \n  '
        result = Julie._parse_result(raw)
        assert result["expanded_task"] == "task"
        assert result["plan"] == ["a", "b"]
        assert result["uncertainty"] == ["u"]

    def test_json_with_markdown_fences(self):
        raw = '```json\n{"expanded_task": "task", "plan": ["step"], "uncertainty": []}\n```'
        result = Julie._parse_result(raw)
        assert result["expanded_task"] == "task"
        assert result["plan"] == ["step"]
        assert result["uncertainty"] == []

    def test_json_with_markdown_fences_no_json_marker(self):
        raw = '```\n{"expanded_task": "task", "plan": ["step"], "uncertainty": []}\n```'
        result = Julie._parse_result(raw)
        assert result["expanded_task"] == "task"

    def test_json_with_json_marker_inside_fences(self):
        raw = '```json\njson\n{"expanded_task": "task", "plan": ["step"], "uncertainty": []}\n```'
        result = Julie._parse_result(raw)
        assert result["expanded_task"] == "task"

    def test_missing_expanded_task_raises(self):
        raw = '{"plan": ["step"], "uncertainty": []}'
        with pytest.raises(ValueError, match="missing a required field"):
            Julie._parse_result(raw)

    def test_missing_plan_raises(self):
        raw = '{"expanded_task": "task", "uncertainty": []}'
        with pytest.raises(ValueError, match="missing a required field"):
            Julie._parse_result(raw)

    def test_missing_uncertainty_raises(self):
        raw = '{"expanded_task": "task", "plan": ["step"]}'
        with pytest.raises(ValueError, match="missing a required field"):
            Julie._parse_result(raw)

    def test_extra_fields_raises(self):
        raw = '{"expanded_task": "task", "plan": ["step"], "uncertainty": [], "extra": "field"}'
        with pytest.raises(ValueError, match="unknown fields"):
            Julie._parse_result(raw)

    def test_expanded_task_not_string_raises(self):
        raw = '{"expanded_task": 123, "plan": ["step"], "uncertainty": []}'
        with pytest.raises(ValueError, match="invalid field types"):
            Julie._parse_result(raw)

    def test_expanded_task_empty_raises(self):
        raw = '{"expanded_task": "", "plan": ["step"], "uncertainty": []}'
        with pytest.raises(ValueError, match="invalid field types"):
            Julie._parse_result(raw)

    def test_expanded_task_whitespace_only_raises(self):
        raw = '{"expanded_task": "   ", "plan": ["step"], "uncertainty": []}'
        with pytest.raises(ValueError, match="invalid field types"):
            Julie._parse_result(raw)

    def test_plan_not_list_raises(self):
        raw = '{"expanded_task": "task", "plan": "not a list", "uncertainty": []}'
        with pytest.raises(ValueError, match="invalid field types"):
            Julie._parse_result(raw)

    def test_plan_empty_allowed(self):
        # Empty plan is currently allowed by the implementation
        raw = '{"expanded_task": "task", "plan": [], "uncertainty": []}'
        result = Julie._parse_result(raw)
        assert result["plan"] == []

    def test_plan_with_non_string_raises(self):
        raw = '{"expanded_task": "task", "plan": ["step", 123], "uncertainty": []}'
        with pytest.raises(ValueError, match="invalid field types"):
            Julie._parse_result(raw)

    def test_plan_with_empty_string_raises(self):
        raw = '{"expanded_task": "task", "plan": ["step", ""], "uncertainty": []}'
        with pytest.raises(ValueError, match="invalid field types"):
            Julie._parse_result(raw)

    def test_plan_with_whitespace_only_raises(self):
        raw = '{"expanded_task": "task", "plan": ["step", "   "], "uncertainty": []}'
        with pytest.raises(ValueError, match="invalid field types"):
            Julie._parse_result(raw)

    def test_uncertainty_not_list_raises(self):
        raw = '{"expanded_task": "task", "plan": ["step"], "uncertainty": "not a list"}'
        with pytest.raises(ValueError, match="invalid field types"):
            Julie._parse_result(raw)

    def test_uncertainty_with_non_string_raises(self):
        raw = '{"expanded_task": "task", "plan": ["step"], "uncertainty": ["valid", 123]}'
        with pytest.raises(ValueError, match="invalid field types"):
            Julie._parse_result(raw)

    def test_uncertainty_with_empty_string_raises(self):
        raw = '{"expanded_task": "task", "plan": ["step"], "uncertainty": ["valid", ""]}'
        with pytest.raises(ValueError, match="invalid field types"):
            Julie._parse_result(raw)

    def test_invalid_json_raises(self):
        raw = '{"expanded_task": "task", "plan": ["step"], "uncertainty": []'  # missing }
        with pytest.raises(ValueError, match="invalid JSON"):
            Julie._parse_result(raw)

    def test_non_object_json_raises(self):
        raw = '["not", "an", "object"]'
        with pytest.raises(ValueError, match="must be an object"):
            Julie._parse_result(raw)

    def test_strips_whitespace_from_fields(self):
        raw = '{"expanded_task": "  task  ", "plan": ["  step  "], "uncertainty": ["  unc  "]}'
        result = Julie._parse_result(raw)
        assert result["expanded_task"] == "task"
        assert result["plan"] == ["step"]
        assert result["uncertainty"] == ["unc"]


class TestJulieReason:
    """Test Julie.reason method input validation."""

    def test_non_string_input_raises(self):
        julie = Julie(backend=MagicMock())
        with pytest.raises(TypeError, match="User input must be a string"):
            julie.reason(123)

    def test_empty_string_returns_empty(self):
        julie = Julie(backend=MagicMock())
        result = julie.reason("")
        assert result == ""

    def test_whitespace_only_returns_empty(self):
        julie = Julie(backend=MagicMock())
        result = julie.reason("   ")
        assert result == ""

    def test_non_string_context_raises(self):
        julie = Julie(backend=MagicMock())
        with pytest.raises(TypeError, match="Context must be a string or None"):
            julie.reason("test", context=123)

    def test_backend_returns_non_string_raises(self):
        mock_backend = MagicMock()
        mock_backend.generate.return_value = 123
        julie = Julie(backend=mock_backend)
        with pytest.raises(TypeError, match="Backend must return a string"):
            julie.reason("test")


from unittest.mock import MagicMock  # for Julie tests