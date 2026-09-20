"""Tests for OllamaClient and Gwen modules."""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock, Mock
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.ollama.client import OllamaClient
from agent.gwen.gwen import Gwen, GwenResult, OllamaCriticBackend


class TestOllamaClient:
    """Test OllamaClient class."""

    @patch("agent.ollama.client.discover_ollama")
    def test_init_selects_qwen_model(self, mock_discover):
        mock_discover.return_value = {
            "host": "http://localhost:11434",
            "models": [{"name": "qwen2.5:7b"}, {"name": "llama3:8b"}]
        }
        client = OllamaClient()
        assert client.model == "qwen2.5:7b"
        assert client.host == "http://localhost:11434"
        assert client.think is False

    @patch("agent.ollama.client.discover_ollama")
    def test_init_selects_first_model_when_no_qwen(self, mock_discover):
        mock_discover.return_value = {
            "host": "http://localhost:11434",
            "models": [{"name": "llama3:8b"}, {"name": "mistral:7b"}]
        }
        client = OllamaClient()
        assert client.model == "llama3:8b"

    @patch("agent.ollama.client.discover_ollama")
    def test_init_uses_provided_model_if_available(self, mock_discover):
        mock_discover.return_value = {
            "host": "http://localhost:11434",
            "models": [{"name": "qwen2.5:7b"}, {"name": "llama3:8b"}]
        }
        client = OllamaClient(model="llama3:8b")
        assert client.model == "llama3:8b"

    @patch("agent.ollama.client.discover_ollama")
    def test_init_falls_back_when_provided_model_not_available(self, mock_discover):
        mock_discover.return_value = {
            "host": "http://localhost:11434",
            "models": [{"name": "qwen2.5:7b"}]
        }
        client = OllamaClient(model="nonexistent")
        assert client.model == "qwen2.5:7b"

    @patch("agent.ollama.client.discover_ollama")
    def test_init_uses_env_var_when_no_model_provided(self, mock_discover):
        mock_discover.return_value = {
            "host": "http://localhost:11434",
            "models": [{"name": "qwen2.5:7b"}, {"name": "llama3:8b"}]
        }
        with patch.dict(os.environ, {"OLLAMA_MODEL": "llama3:8b"}):
            client = OllamaClient()
            assert client.model == "llama3:8b"

    @patch("agent.ollama.client.discover_ollama")
    def test_init_raises_when_no_models(self, mock_discover):
        mock_discover.return_value = {
            "host": "http://localhost:11434",
            "models": []
        }
        with pytest.raises(RuntimeError, match="No Ollama model is found"):
            OllamaClient()

    @patch("agent.ollama.client.discover_ollama")
    def test_init_raises_when_models_have_no_names(self, mock_discover):
        mock_discover.return_value = {
            "host": "http://localhost:11434",
            "models": [{}, {}]
        }
        with pytest.raises(RuntimeError, match="No Ollama model is found"):
            OllamaClient()

    @patch("agent.ollama.client.discover_ollama")
    @patch("urllib.request.urlopen")
    def test_chat_success(self, mock_urlopen, mock_discover):
        mock_discover.return_value = {
            "host": "http://localhost:11434",
            "models": [{"name": "qwen2.5:7b"}]
        }
        mock_response = Mock()
        mock_response.read.return_value = b'{"message": {"content": "Hello"}}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = OllamaClient()
        result = client.chat([{"role": "user", "content": "Hi"}])
        assert result == {"message": {"content": "Hello"}}

    @patch("agent.ollama.client.discover_ollama")
    @patch("urllib.request.urlopen")
    def test_chat_http_error(self, mock_urlopen, mock_discover):
        mock_discover.return_value = {
            "host": "http://localhost:11434",
            "models": [{"name": "qwen2.5:7b"}]
        }
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://localhost:11434/api/chat", 500, "Internal Server Error", {}, None
        )

        client = OllamaClient()
        with pytest.raises(RuntimeError, match="Ollama API error"):
            client.chat([{"role": "user", "content": "Hi"}])

    @patch("agent.ollama.client.discover_ollama")
    @patch("urllib.request.urlopen")
    def test_chat_url_error(self, mock_urlopen, mock_discover):
        mock_discover.return_value = {
            "host": "http://localhost:11434",
            "models": [{"name": "qwen2.5:7b"}]
        }
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        client = OllamaClient()
        with pytest.raises(RuntimeError, match="Could not connect to Ollama"):
            client.chat([{"role": "user", "content": "Hi"}])

    @patch("agent.ollama.client.discover_ollama")
    @patch("urllib.request.urlopen")
    def test_ask_method(self, mock_urlopen, mock_discover):
        mock_discover.return_value = {
            "host": "http://localhost:11434",
            "models": [{"name": "qwen2.5:7b"}]
        }
        mock_response = Mock()
        mock_response.read.return_value = b'{"message": {"content": "Hello world"}}'
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        client = OllamaClient()
        result = client.ask("Hi")
        assert result == "Hello world"

    @patch("agent.ollama.client.discover_ollama")
    def test_think_property(self, mock_discover):
        mock_discover.return_value = {
            "host": "http://localhost:11434",
            "models": [{"name": "qwen2.5:7b"}]
        }
        client = OllamaClient(think=True)
        assert client.think is True
        client.think = False
        assert client.think is False


class TestGwen:
    """Test Gwen critic agent."""

    def test_review_with_empty_user_input(self):
        backend = MagicMock()
        gwen = Gwen(backend)
        result = gwen.review("", "some reasoning")
        assert result.approved is False
        assert result.critique == "User input is empty."

    def test_review_with_empty_reasoning(self):
        backend = MagicMock()
        gwen = Gwen(backend)
        result = gwen.review("user request", "")
        assert result.approved is False
        assert result.critique == "Julie returned empty reasoning."

    def test_review_with_non_string_user_input(self):
        backend = MagicMock()
        gwen = Gwen(backend)
        with pytest.raises(TypeError, match="User input must be a string"):
            gwen.review(123, "reasoning")

    def test_review_with_non_string_reasoning(self):
        backend = MagicMock()
        gwen = Gwen(backend)
        with pytest.raises(TypeError, match="Reasoning must be a string"):
            gwen.review("user request", 123)

    def test_review_backend_exception_propagates(self):
        backend = MagicMock()
        backend.generate.side_effect = RuntimeError("Backend failed")
        gwen = Gwen(backend)
        with pytest.raises(RuntimeError, match="Backend failed"):
            gwen.review("user request", "reasoning")

    def test_review_backend_returns_non_string(self):
        backend = MagicMock()
        backend.generate.return_value = 123
        gwen = Gwen(backend)
        with pytest.raises(TypeError, match="Backend must return a string"):
            gwen.review("user request", "reasoning")

    def test_review_backend_returns_empty(self):
        backend = MagicMock()
        backend.generate.return_value = ""
        gwen = Gwen(backend)
        result = gwen.review("user request", "reasoning")
        assert result.approved is False
        assert result.critique == "Gwen returned an empty review"

    def test_review_parses_approved_true(self):
        backend = MagicMock()
        backend.generate.return_value = "APPROVED: true\nCRITIQUE: Looks good"
        gwen = Gwen(backend)
        result = gwen.review("user request", "reasoning")
        assert result.approved is True
        assert "Looks good" in result.critique

    def test_review_parses_approved_false(self):
        backend = MagicMock()
        backend.generate.return_value = "APPROVED: false\nCRITIQUE: Has issues"
        gwen = Gwen(backend)
        result = gwen.review("user request", "reasoning")
        assert result.approved is False
        assert "Has issues" in result.critique

    def test_review_missing_approved_treated_as_false(self):
        backend = MagicMock()
        backend.generate.return_value = "CRITIQUE: No approved line"
        gwen = Gwen(backend)
        result = gwen.review("user request", "reasoning")
        assert result.approved is False

    def test_review_case_insensitive_approved(self):
        backend = MagicMock()
        backend.generate.return_value = "approved: True\ncritique: ok"
        gwen = Gwen(backend)
        result = gwen.review("user request", "reasoning")
        assert result.approved is True

    def test_review_with_extra_whitespace(self):
        backend = MagicMock()
        backend.generate.return_value = "  APPROVED: true  \n  CRITIQUE: ok  "
        gwen = Gwen(backend)
        result = gwen.review("user request", "reasoning")
        assert result.approved is True


class TestGwenStructured:
    """Test Gwen.review_structured method."""

    def test_review_structured_with_empty_user_request(self):
        backend = MagicMock()
        gwen = Gwen(backend)
        from agent.julie.julie import JulieResult
        from agent.selina.selina import SelinaResult
        julie_result = JulieResult(
            user_request="test", context=None, expanded_task="task", plan=["step"], uncertainty=[], raw_response="raw"
        )
        selina_result = SelinaResult(
            success=True, expanded_task="task", interpretation="interp", action="list_directory", result="ok"
        )
        result = gwen.review_structured("", julie_result, selina_result)
        assert result.approved is False
        assert result.critique == "User request is empty."

    def test_review_structured_invalid_julie_result(self):
        backend = MagicMock()
        gwen = Gwen(backend)
        from agent.selina.selina import SelinaResult
        selina_result = SelinaResult(
            success=True, expanded_task="task", interpretation="interp", action="list_directory", result="ok"
        )
        with pytest.raises(TypeError, match="julie_result must be a JulieResult"):
            gwen.review_structured("request", "not a JulieResult", selina_result)

    def test_review_structured_invalid_selina_result(self):
        backend = MagicMock()
        gwen = Gwen(backend)
        from agent.julie.julie import JulieResult
        julie_result = JulieResult(
            user_request="test", context=None, expanded_task="task", plan=["step"], uncertainty=[], raw_response="raw"
        )
        with pytest.raises(TypeError, match="selina_result must be a SelinaResult"):
            gwen.review_structured("request", julie_result, "not a SelinaResult")

    def test_review_structured_invalid_annie_result(self):
        backend = MagicMock()
        gwen = Gwen(backend)
        from agent.julie.julie import JulieResult
        from agent.selina.selina import SelinaResult
        julie_result = JulieResult(
            user_request="test", context=None, expanded_task="task", plan=["step"], uncertainty=[], raw_response="raw"
        )
        selina_result = SelinaResult(
            success=True, expanded_task="task", interpretation="interp", action="list_directory", result="ok"
        )
        with pytest.raises(TypeError, match="annie_result must be an AnnieResult or None"):
            gwen.review_structured("request", julie_result, selina_result, annie_result="not an AnnieResult")

    def test_review_structured_parses_json_response(self):
        backend = MagicMock()
        backend.generate.return_value = json.dumps({
            "approved": True,
            "issues": ["issue1"],
            "safety_concerns": ["safety1"],
            "recommendations": ["rec1"]
        })
        gwen = Gwen(backend)
        
        from agent.julie.julie import JulieResult
        from agent.selina.selina import SelinaResult
        
        julie_result = JulieResult(
            user_request="test", context=None, expanded_task="task", plan=["step"], uncertainty=[], raw_response="raw"
        )
        selina_result = SelinaResult(
            success=True, expanded_task="task", interpretation="interp", action="list_directory", result="ok"
        )
        
        result = gwen.review_structured("request", julie_result, selina_result)
        assert result.approved is True
        assert result.issues == ["issue1"]
        assert result.safety_concerns == ["safety1"]
        assert result.recommendations == ["rec1"]

    def test_review_structured_handles_markdown_fences(self):
        backend = MagicMock()
        backend.generate.return_value = '```json\n{"approved": true, "issues": [], "safety_concerns": [], "recommendations": []}\n```'
        gwen = Gwen(backend)
        
        from agent.julie.julie import JulieResult
        from agent.selina.selina import SelinaResult
        
        julie_result = JulieResult(
            user_request="test", context=None, expanded_task="task", plan=["step"], uncertainty=[], raw_response="raw"
        )
        selina_result = SelinaResult(
            success=True, expanded_task="task", interpretation="interp", action="list_directory", result="ok"
        )
        
        result = gwen.review_structured("request", julie_result, selina_result)
        assert result.approved is True

    def test_review_structured_fallback_on_invalid_json(self):
        backend = MagicMock()
        backend.generate.return_value = "APPROVED: true\nCRITIQUE: some critique"
        gwen = Gwen(backend)
        
        from agent.julie.julie import JulieResult
        from agent.selina.selina import SelinaResult
        
        julie_result = JulieResult(
            user_request="test", context=None, expanded_task="task", plan=["step"], uncertainty=[], raw_response="raw"
        )
        selina_result = SelinaResult(
            success=True, expanded_task="task", interpretation="interp", action="list_directory", result="ok"
        )
        
        result = gwen.review_structured("request", julie_result, selina_result)
        assert result.approved is True

    def test_review_structured_backend_returns_empty(self):
        backend = MagicMock()
        backend.generate.return_value = ""
        gwen = Gwen(backend)
        
        from agent.julie.julie import JulieResult
        from agent.selina.selina import SelinaResult
        
        julie_result = JulieResult(
            user_request="test", context=None, expanded_task="task", plan=["step"], uncertainty=[], raw_response="raw"
        )
        selina_result = SelinaResult(
            success=True, expanded_task="task", interpretation="interp", action="list_directory", result="ok"
        )
        
        result = gwen.review_structured("request", julie_result, selina_result)
        assert result.approved is False
        assert result.critique == "Gwen returned an empty review."

    def test_review_structured_backend_returns_non_string(self):
        backend = MagicMock()
        backend.generate.return_value = 123
        gwen = Gwen(backend)
        
        from agent.julie.julie import JulieResult
        from agent.selina.selina import SelinaResult
        
        julie_result = JulieResult(
            user_request="test", context=None, expanded_task="task", plan=["step"], uncertainty=[], raw_response="raw"
        )
        selina_result = SelinaResult(
            success=True, expanded_task="task", interpretation="interp", action="list_directory", result="ok"
        )
        
        with pytest.raises(TypeError, match="Backend must return a string"):
            gwen.review_structured("request", julie_result, selina_result)


class TestGwenParseStructuredResponse:
    """Test Gwen._parse_structured_response static method."""

    def test_parses_valid_json(self):
        raw = '{"approved": true, "issues": ["i1"], "safety_concerns": ["s1"], "recommendations": ["r1"]}'
        result = Gwen._parse_structured_response(raw)
        assert result["approved"] is True
        assert result["issues"] == ["i1"]
        assert result["safety_concerns"] == ["s1"]
        assert result["recommendations"] == ["r1"]

    def test_parses_json_with_markdown_fences(self):
        raw = '```json\n{"approved": false, "issues": [], "safety_concerns": [], "recommendations": []}\n```'
        result = Gwen._parse_structured_response(raw)
        assert result["approved"] is False

    def test_approved_as_string_true(self):
        raw = '{"approved": "true", "issues": [], "safety_concerns": [], "recommendations": []}'
        result = Gwen._parse_structured_response(raw)
        assert result["approved"] is True

    def test_approved_as_string_false(self):
        raw = '{"approved": "false", "issues": [], "safety_concerns": [], "recommendations": []}'
        result = Gwen._parse_structured_response(raw)
        assert result["approved"] is False

    def test_missing_fields_defaults_to_empty(self):
        raw = '{}'
        result = Gwen._parse_structured_response(raw)
        assert result["approved"] is False
        assert result["issues"] == []
        assert result["safety_concerns"] == []
        assert result["recommendations"] == []

    def test_non_list_fields_filtered(self):
        # Use null instead of None for valid JSON
        raw = '{"approved": true, "issues": ["valid", 123, null], "safety_concerns": [], "recommendations": []}'
        result = Gwen._parse_structured_response(raw)
        # The _str_list helper converts non-strings to strings, filters None/null
        assert "valid" in result["issues"]
        assert "123" in result["issues"]  # 123 converted to "123"
        assert len(result["issues"]) == 2  # null is filtered out

    def test_fallback_parses_approved_line(self):
        raw = 'APPROVED: true\nCRITIQUE: some critique'
        result = Gwen._parse_structured_response(raw)
        assert result["approved"] is True
        assert "some critique" in result["issues"]

    def test_fallback_approved_false(self):
        raw = 'APPROVED: false\nCRITIQUE: some critique'
        result = Gwen._parse_structured_response(raw)
        assert result["approved"] is False

    def test_fallback_no_approved_returns_false(self):
        raw = 'Just some text'
        result = Gwen._parse_structured_response(raw)
        assert result["approved"] is False
        assert "Just some text" in result["issues"]


class TestGwenBuildCritiqueText:
    """Test Gwen._build_critique_text static method."""

    def test_builds_critique_from_parts(self):
        parsed = {
            "issues": ["issue1", "issue2"],
            "safety_concerns": ["safety1"],
            "recommendations": ["rec1"]
        }
        result = Gwen._build_critique_text(parsed)
        assert "Issue: issue1" in result
        assert "Issue: issue2" in result
        assert "Safety: safety1" in result
        assert "Recommendation: rec1" in result

    def test_empty_parts_returns_default(self):
        parsed = {"issues": [], "safety_concerns": [], "recommendations": []}
        result = Gwen._build_critique_text(parsed)
        assert result == "No detailed critique provided."


class TestGwenParseApproval:
    """Test Gwen._parse_approval static method."""

    def test_parses_approved_true(self):
        result = Gwen._parse_approval("APPROVED: true")
        assert result is True

    def test_parses_approved_false(self):
        result = Gwen._parse_approval("APPROVED: false")
        assert result is False

    def test_case_insensitive(self):
        assert Gwen._parse_approval("approved: TRUE") is True
        assert Gwen._parse_approval("Approved: True") is True

    def test_missing_approved_returns_false(self):
        assert Gwen._parse_approval("CRITIQUE: something") is False
        assert Gwen._parse_approval("") is False


class TestGwenParseCritique:
    """Test Gwen._parse_critique static method."""

    def test_extracts_critique(self):
        result = Gwen._parse_critique("APPROVED: true\nCRITIQUE: This is the critique")
        assert result == "This is the critique"

    def test_missing_critique_returns_empty(self):
        result = Gwen._parse_critique("APPROVED: true")
        assert result == ""

    def test_case_insensitive(self):
        result = Gwen._parse_critique("critique: Lowercase critique")
        assert result == "Lowercase critique"