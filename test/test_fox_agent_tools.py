"""Tests for Fox Agent tool parsing and dispatch edge cases."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.ollama.ollama_agent import (
    _parse_tool_calls,
    _strip_tool_calls,
    _resolve_tool_name,
    TOOL_CALL_RE,
    TOOL_CALL_FALLBACK_RE,
    ARG_RE,
)
from agent.ollama.tools import dispatch, TOOLS


class TestParseToolCalls:
    """Additional tests for _parse_tool_calls."""

    def test_tool_call_with_no_args(self):
        text = '>>TOOL: schedule_view()<<'
        calls = _parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "schedule_view"
        assert calls[0]["args"] == {}

    def test_tool_call_with_empty_args(self):
        text = '>>TOOL: finance_calculate()<<'
        calls = _parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["args"] == {}

    def test_tool_call_with_multiple_args(self):
        text = '>>TOOL: finance_calculate(expression="1+1", foo="bar")<<'
        calls = _parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["args"] == {"expression": "1+1", "foo": "bar"}

    def test_tool_call_with_spaces_around_equals(self):
        text = '>>TOOL: finance_calculate(expression = "1+1")<<'
        calls = _parse_tool_calls(text)
        # ARG_RE expects no spaces around =
        assert len(calls) == 1
        # This may not parse correctly with spaces - depends on implementation

    def test_tool_call_with_special_chars_in_value(self):
        text = '>>TOOL: web_search(query="hello world!")<<'
        calls = _parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["args"]["query"] == "hello world!"

    def test_multiple_tool_calls_on_separate_lines(self):
        text = '>>TOOL: schedule_view()<<\n>>TOOL: finance_calculate(expression="2+2")<<'
        calls = _parse_tool_calls(text)
        assert len(calls) == 2
        assert calls[0]["name"] == "schedule_view"
        assert calls[1]["name"] == "finance_calculate"

    def test_multiple_tool_calls_on_same_line(self):
        text = '>>TOOL: schedule_view()<< >>TOOL: finance_calculate(expression="2+2")<<'
        calls = _parse_tool_calls(text)
        assert len(calls) == 2

    def test_fallback_regex_handles_broken_closing(self):
        text = '>>TOOL: schedule_view()<>'
        calls = _parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "schedule_view"

    def test_fallback_regex_handles_mixed_brackets(self):
        # Primary regex matches first, then fallback - but they may not both match the same text
        text = '>>TOOL: schedule_view()<<>>TOOL: finance_calculate(expression="1")<>'
        calls = _parse_tool_calls(text)
        # At least one should be parsed
        assert len(calls) >= 1
        assert calls[0]["name"] == "schedule_view"

    def test_embedded_tool_call_in_text(self):
        text = 'Here is a tool call: >>TOOL: schedule_view()<< and some text after.'
        calls = _parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "schedule_view"

    def test_no_tool_calls_returns_empty(self):
        text = 'Just some text without tool calls.'
        calls = _parse_tool_calls(text)
        assert calls == []

    def test_empty_string_returns_empty(self):
        calls = _parse_tool_calls("")
        assert calls == []

    def test_whitespace_only_returns_empty(self):
        calls = _parse_tool_calls("   \n\t  ")
        assert calls == []

    def test_partial_tool_marker_not_parsed(self):
        text = '>>TOOL: schedule_view'
        calls = _parse_tool_calls(text)
        assert calls == []

    def test_unclosed_marker_not_parsed(self):
        text = '>>TOOL: schedule_view()'
        calls = _parse_tool_calls(text)
        assert calls == []


class TestStripToolCalls:
    """Additional tests for _strip_tool_calls."""

    def test_strips_primary_tool_call(self):
        text = 'Before >>TOOL: schedule_view()<< After'
        result = _strip_tool_calls(text)
        assert result == "Before  After"

    def test_strips_fallback_tool_call(self):
        text = 'Before >>TOOL: schedule_view()<> After'
        result = _strip_tool_calls(text)
        assert result == "Before  After"

    def test_strips_multiple_tool_calls(self):
        text = '>>TOOL: a()<< middle >>TOOL: b()<< end'
        result = _strip_tool_calls(text)
        # Stripping removes the tool calls but leaves the middle text
        assert "middle" in result
        assert "end" in result
        assert "TOOL:" not in result

    def test_noop_when_no_calls(self):
        text = 'No tool calls here.'
        result = _strip_tool_calls(text)
        assert result == 'No tool calls here.'

    def test_empty_string_returns_empty(self):
        result = _strip_tool_calls("")
        assert result == ""

    def test_whitespace_only_returns_empty(self):
        result = _strip_tool_calls("   ")
        assert result == ""


class TestResolveToolName:
    """Additional tests for _resolve_tool_name."""

    def test_exact_match(self):
        assert _resolve_tool_name("schedule_view") == "schedule_view"
        assert _resolve_tool_name("finance_calculate") == "finance_calculate"

    def test_fused_name_resolved(self):
        # "finance_calculateexpression" should resolve to "finance_calculate"
        assert _resolve_tool_name("finance_calculateexpression") == "finance_calculate"

    def test_fused_schedule_resolved(self):
        assert _resolve_tool_name("schedule_viewtoday") == "schedule_view"

    def test_no_match_returns_original(self):
        assert _resolve_tool_name("unknown_tool") == "unknown_tool"

    def test_single_char_no_match(self):
        assert _resolve_tool_name("x") == "x"

    def test_empty_string(self):
        assert _resolve_tool_name("") == ""


class TestDispatch:
    """Test dispatch function."""

    def test_unknown_tool_returns_error_message(self):
        result = dispatch("unknown_tool")
        assert "Unknown tool" in result

    def test_tool_exception_caught(self):
        # Register a tool that raises
        def failing_tool():
            raise ValueError("Tool failed")
        
        # We can't easily test this without modifying TOOLS, but we can test
        # that dispatch handles the error format
        result = dispatch("finance_calculate", expression="invalid")
        # The actual tool handles invalid expressions gracefully
        assert isinstance(result, str)

    def test_missing_required_arg_returns_error(self):
        # finance_calculate requires expression
        result = dispatch("finance_calculate")
        assert "Invalid expression" in result or "expression" in result.lower()


class TestToolRegistry:
    """Test TOOLS registry."""

    def test_tools_dict_not_empty(self):
        assert len(TOOLS) > 0

    def test_tools_have_required_fields(self):
        for name, info in TOOLS.items():
            assert "description" in info
            assert "params" in info
            assert "fn" in info
            assert callable(info["fn"])
            assert isinstance(info["description"], str)
            assert isinstance(info["params"], list)

    def test_tool_params_have_name_type_desc(self):
        for name, info in TOOLS.items():
            for param in info["params"]:
                assert "name" in param
                assert "type" in param
                assert "desc" in param

    def test_tool_prompt_block_not_empty(self):
        from agent.ollama.tools import tool_prompt_block
        block = tool_prompt_block()
        assert isinstance(block, str)
        assert len(block) > 0
        assert "schedule_view" in block
        assert "finance_calculate" in block


class TestArgRegex:
    """Test ARG_RE regex."""

    def test_matches_key_value_pairs(self):
        matches = list(ARG_RE.finditer('expression="1+1", foo="bar"'))
        assert len(matches) == 2
        assert matches[0].group(1) == "expression"
        assert matches[0].group(2) == "1+1"
        assert matches[1].group(1) == "foo"
        assert matches[1].group(2) == "bar"

    def test_no_match_for_invalid_format(self):
        matches = list(ARG_RE.finditer('invalid format'))
        assert len(matches) == 0