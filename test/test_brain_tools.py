"""Tests for brain tools module."""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.tools import TOOLS, dispatcher


class TestToolsRegistry:
    """Test TOOLS registry."""

    def test_tools_list_not_empty(self):
        assert len(TOOLS) > 0

    def test_tools_have_required_fields(self):
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert isinstance(tool["name"], str)
            assert isinstance(tool["description"], str)
            assert isinstance(tool["input_schema"], dict)

    def test_tool_names_are_unique(self):
        names = [tool["name"] for tool in TOOLS]
        assert len(names) == len(set(names))

    def test_expected_tools_present(self):
        names = {tool["name"] for tool in TOOLS}
        assert "browse" in names
        assert "finance_calculate" in names
        assert "schedule_view" in names

    def test_browse_tool_schema(self):
        browse = next(t for t in TOOLS if t["name"] == "browse")
        assert browse["input_schema"]["type"] == "object"
        assert "url" in browse["input_schema"]["properties"]
        assert browse["input_schema"]["required"] == ["url"]

    def test_finance_calculate_tool_schema(self):
        finance = next(t for t in TOOLS if t["name"] == "finance_calculate")
        assert finance["input_schema"]["type"] == "object"
        assert "expression" in finance["input_schema"]["properties"]
        assert finance["input_schema"]["required"] == ["expression"]

    def test_schedule_view_tool_schema(self):
        schedule = next(t for t in TOOLS if t["name"] == "schedule_view")
        assert schedule["input_schema"]["type"] == "object"
        assert "query" in schedule["input_schema"]["properties"]
        assert schedule["input_schema"]["required"] == ["query"]


class TestDispatcher:
    """Test dispatcher function."""

    @patch("brain.tools.requests.post")
    def test_dispatch_browse_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"title": "Test Page", "text": "Page content"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = dispatcher("browse", {"url": "https://example.com"})

        assert "Title: Test Page" in result
        assert "Page content" in result
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "json" in kwargs
        assert kwargs["json"]["url"] == "https://example.com"

    @patch("brain.tools.requests.post")
    def test_dispatch_browse_http_error(self, mock_post):
        import requests
        mock_post.side_effect = requests.HTTPError("404 Not Found")

        with pytest.raises(requests.HTTPError):
            dispatcher("browse", {"url": "https://example.com"})

    @patch("brain.tools.requests.post")
    def test_dispatch_browse_connection_error(self, mock_post):
        import requests
        mock_post.side_effect = requests.ConnectionError("Connection refused")

        with pytest.raises(requests.ConnectionError):
            dispatcher("browse", {"url": "https://example.com"})

    def test_dispatch_finance_calculate(self):
        # Currently returns placeholder
        result = dispatcher("finance_calculate", {"expression": "2+2"})
        assert "In Progress" in result or "Finance_Bot" in result

    def test_dispatch_schedule_view(self):
        # Currently returns placeholder
        result = dispatcher("schedule_view", {"query": "today"})
        assert "In Progress" in result or "Schedule_Bot" in result

    def test_dispatch_unknown_tool(self):
        result = dispatcher("unknown_tool", {})
        assert "Unknown tool" in result
        assert "unknown_tool" in result

    def test_dispatch_missing_url_for_browse(self):
        # Should raise KeyError for missing required parameter
        with pytest.raises(KeyError):
            dispatcher("browse", {})


class TestDispatcherEdgeCases:
    """Edge case tests for dispatcher."""

    def test_case_sensitive_tool_names(self):
        result = dispatcher("BROWSE", {"url": "https://example.com"})
        assert "Unknown tool" in result

    def test_empty_tool_name(self):
        result = dispatcher("", {})
        assert "Unknown tool" in result

    @patch("brain.tools.requests.post")
    def test_browse_timeout(self, mock_post):
        import requests
        mock_post.side_effect = requests.Timeout()

        with pytest.raises(requests.Timeout):
            dispatcher("browse", {"url": "https://example.com"})

    @patch("brain.tools.requests.post")
    def test_browse_returns_expected_format(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {"title": "Example", "text": "Content here"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = dispatcher("browse", {"url": "https://example.com"})

        assert result == "Title: Example\n\nContent here"