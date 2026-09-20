"""Tests for Annie's _parse_response and _build_user_message."""

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.annie.annie import Annie, AnnieResult
from agent.julie.julie import JulieResult


class TestAnnieParseResponse:
    """Test Annie._parse_response static method."""

    def test_valid_json_response(self):
        raw = json.dumps({
            "interpretation": "interpret",
            "requirements": ["req1"],
            "constraints": ["const1"],
            "technical_handoff": "handoff",
            "clarification_needed": ["clarify"]
        })
        result = Annie._parse_response(raw)
        assert result["interpretation"] == "interpret"
        assert result["requirements"] == ["req1"]
        assert result["constraints"] == ["const1"]
        assert result["technical_handoff"] == "handoff"
        assert result["clarification_needed"] == ["clarify"]

    def test_valid_json_with_whitespace(self):
        raw = '  \n  {"interpretation": "i", "requirements": [], "constraints": [], "technical_handoff": "h", "clarification_needed": []}  \n  '
        result = Annie._parse_response(raw)
        assert result["interpretation"] == "i"

    def test_json_with_markdown_fences(self):
        raw = '```json\n{"interpretation": "i", "requirements": [], "constraints": [], "technical_handoff": "h", "clarification_needed": []}\n```'
        result = Annie._parse_response(raw)
        assert result["interpretation"] == "i"

    def test_json_with_markdown_fences_no_json_marker(self):
        raw = '```\n{"interpretation": "i", "requirements": [], "constraints": [], "technical_handoff": "h", "clarification_needed": []}\n```'
        result = Annie._parse_response(raw)
        assert result["interpretation"] == "i"

    def test_missing_interpretation_raises(self):
        raw = json.dumps({"requirements": [], "constraints": [], "technical_handoff": "h", "clarification_needed": []})
        with pytest.raises(ValueError, match="Missing required fields"):
            Annie._parse_response(raw)

    def test_missing_requirements_raises(self):
        raw = json.dumps({"interpretation": "i", "constraints": [], "technical_handoff": "h", "clarification_needed": []})
        with pytest.raises(ValueError, match="Missing required fields"):
            Annie._parse_response(raw)

    def test_missing_constraints_raises(self):
        raw = json.dumps({"interpretation": "i", "requirements": [], "technical_handoff": "h", "clarification_needed": []})
        with pytest.raises(ValueError, match="Missing required fields"):
            Annie._parse_response(raw)

    def test_missing_technical_handoff_raises(self):
        raw = json.dumps({"interpretation": "i", "requirements": [], "constraints": [], "clarification_needed": []})
        with pytest.raises(ValueError, match="Missing required fields"):
            Annie._parse_response(raw)

    def test_missing_clarification_needed_raises(self):
        raw = json.dumps({"interpretation": "i", "requirements": [], "constraints": [], "technical_handoff": "h"})
        with pytest.raises(ValueError, match="Missing required fields"):
            Annie._parse_response(raw)

    def test_non_dict_json_raises(self):
        raw = '["not", "an", "object"]'
        with pytest.raises(ValueError, match="Excepted a Json"):
            Annie._parse_response(raw)

    def test_interpretation_not_string_raises(self):
        raw = json.dumps({"interpretation": 123, "requirements": [], "constraints": [], "technical_handoff": "h", "clarification_needed": []})
        with pytest.raises(TypeError, match="interpretation must be a string"):
            Annie._parse_response(raw)

    def test_technical_handoff_not_string_raises(self):
        raw = json.dumps({"interpretation": "i", "requirements": [], "constraints": [], "technical_handoff": 123, "clarification_needed": []})
        with pytest.raises(TypeError, match="technical_handoff must be a string"):
            Annie._parse_response(raw)

    def test_requirements_not_list_raises(self):
        raw = json.dumps({"interpretation": "i", "requirements": "not a list", "constraints": [], "technical_handoff": "h", "clarification_needed": []})
        with pytest.raises(TypeError, match="requirements must be a list"):
            Annie._parse_response(raw)

    def test_constraints_not_list_raises(self):
        raw = json.dumps({"interpretation": "i", "requirements": [], "constraints": "not a list", "technical_handoff": "h", "clarification_needed": []})
        with pytest.raises(TypeError, match="constraints must be a list"):
            Annie._parse_response(raw)

    def test_clarification_needed_not_list_raises(self):
        raw = json.dumps({"interpretation": "i", "requirements": [], "constraints": [], "technical_handoff": "h", "clarification_needed": "not a list"})
        with pytest.raises(TypeError, match="clarification_needed must be a list"):
            Annie._parse_response(raw)

    def test_requirements_with_non_string_raises(self):
        raw = json.dumps({"interpretation": "i", "requirements": ["valid", 123], "constraints": [], "technical_handoff": "h", "clarification_needed": []})
        with pytest.raises(TypeError, match="requirements must contain only strings"):
            Annie._parse_response(raw)

    def test_constraints_with_non_string_raises(self):
        raw = json.dumps({"interpretation": "i", "requirements": [], "constraints": ["valid", 123], "technical_handoff": "h", "clarification_needed": []})
        with pytest.raises(TypeError, match="constraints must contain only strings"):
            Annie._parse_response(raw)

    def test_clarification_needed_with_non_string_raises(self):
        raw = json.dumps({"interpretation": "i", "requirements": [], "constraints": [], "technical_handoff": "h", "clarification_needed": ["valid", 123]})
        with pytest.raises(TypeError, match="clarification_needed must contain only strings"):
            Annie._parse_response(raw)

    def test_invalid_json_raises(self):
        raw = '{"interpretation": "i", "requirements": [], "constraints": [], "technical_handoff": "h", "clarification_needed": []'  # missing }
        with pytest.raises(ValueError, match="invalid json"):
            Annie._parse_response(raw)

    def test_non_string_input_raises(self):
        with pytest.raises(TypeError, match="Backend response must be a string"):
            Annie._parse_response(123)

    def test_empty_lists_allowed(self):
        raw = json.dumps({
            "interpretation": "i",
            "requirements": [],
            "constraints": [],
            "technical_handoff": "h",
            "clarification_needed": []
        })
        result = Annie._parse_response(raw)
        assert result["requirements"] == []
        assert result["constraints"] == []
        assert result["clarification_needed"] == []


class TestAnnieBuildUserMessage:
    """Test Annie._build_user_message static method."""

    def test_builds_message_with_all_fields(self):
        julie_result = JulieResult(
            user_request="list files",
            context="some context",
            expanded_task="list all files in directory",
            plan=["step 1", "step 2"],
            uncertainty=["uncertainty 1"],
            raw_response="raw"
        )
        message = Annie._build_user_message(julie_result)
        assert "list files" in message
        assert "list all files in directory" in message
        assert "step 1" in message
        assert "step 2" in message
        # Context is not included in the message by current implementation

    def test_builds_message_without_context(self):
        julie_result = JulieResult(
            user_request="list files",
            context=None,
            expanded_task="list all files in directory",
            plan=["step 1"],
            uncertainty=[],
            raw_response="raw"
        )
        message = Annie._build_user_message(julie_result)
        assert "list files" in message
        assert "list all files in directory" in message
        assert "step 1" in message
        assert "Context:" not in message or "None" not in message


class TestAnnieStructure:
    """Test Annie.structure method input validation."""

    def test_non_julie_result_raises(self):
        from unittest.mock import MagicMock
        annie = Annie(backend=MagicMock())
        with pytest.raises(TypeError, match="Expected a JulieResult"):
            annie.structure("not a JulieResult")

    def test_non_string_user_request_raises(self):
        from unittest.mock import MagicMock
        julie_result = JulieResult(
            user_request=123,  # invalid type
            context=None,
            expanded_task="task",
            plan=["step"],
            uncertainty=[],
            raw_response="raw"
        )
        annie = Annie(backend=MagicMock())
        with pytest.raises(TypeError, match="Julie user_request must be a string"):
            annie.structure(julie_result)

    def test_empty_user_request_raises(self):
        from unittest.mock import MagicMock
        julie_result = JulieResult(
            user_request="",
            context=None,
            expanded_task="task",
            plan=["step"],
            uncertainty=[],
            raw_response="raw"
        )
        annie = Annie(backend=MagicMock())
        with pytest.raises(ValueError, match="Cannot structure an empty user request"):
            annie.structure(julie_result)


class TestAnnieRefine:
    """Test Annie.refine method input validation."""

    def test_non_annie_result_raises(self):
        from unittest.mock import MagicMock
        annie = Annie(backend=MagicMock())
        with pytest.raises(TypeError, match="Expected an AnnieResult"):
            annie.refine("not an AnnieResult", "feedback")

    def test_non_string_feedback_raises(self):
        from unittest.mock import MagicMock
        annie = Annie(backend=MagicMock())
        previous = AnnieResult(
            user_request="req",
            interpretation="interp",
            requirements=[],
            constraints=[],
            technical_handoff="handoff",
            clarification_needed=[],
            raw_response="raw"
        )
        with pytest.raises(TypeError, match="Selina feedback must be a string"):
            annie.refine(previous, 123)

    def test_empty_feedback_raises(self):
        from unittest.mock import MagicMock
        annie = Annie(backend=MagicMock())
        previous = AnnieResult(
            user_request="req",
            interpretation="interp",
            requirements=[],
            constraints=[],
            technical_handoff="handoff",
            clarification_needed=[],
            raw_response="raw"
        )
        with pytest.raises(ValueError, match="Selina feedback cannot be empty"):
            annie.refine(previous, "   ")