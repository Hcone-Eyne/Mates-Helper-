"""Tests for Ollama discovery module."""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.ollama.discovery import (
    find_ollama_binary,
    get_ollama_host,
    check_server,
    get_models,
    discover_ollama,
    DEFAULT_HOST,
)


class TestFindOllamaBinary:
    """Test find_ollama_binary function."""

    @patch("shutil.which", return_value="/usr/bin/ollama")
    def test_returns_path_when_found(self, mock_which):
        result = find_ollama_binary()
        assert result == "/usr/bin/ollama"
        mock_which.assert_called_once_with("ollama")

    @patch("shutil.which", return_value=None)
    def test_returns_none_when_not_found(self, mock_which):
        result = find_ollama_binary()
        assert result is None


class TestGetOllamaHost:
    """Test get_ollama_host function."""

    def test_returns_default_host(self):
        with patch.dict(os.environ, {}, clear=True):
            result = get_ollama_host()
            assert result == DEFAULT_HOST

    def test_returns_env_host(self):
        with patch.dict(os.environ, {"OLLAMA_HOST": "http://custom:11434"}):
            result = get_ollama_host()
            assert result == "http://custom:11434"

    def test_strips_trailing_slash(self):
        with patch.dict(os.environ, {"OLLAMA_HOST": "http://custom:11434/"}):
            result = get_ollama_host()
            assert result == "http://custom:11434"


class TestCheckServer:
    """Test check_server function."""

    @patch("urllib.request.urlopen")
    def test_returns_true_on_200(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = check_server("http://localhost:11434")
        assert result is True

    @patch("urllib.request.urlopen")
    def test_returns_false_on_non_200(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = check_server("http://localhost:11434")
        assert result is False

    @patch("urllib.request.urlopen")
    def test_returns_false_on_urlerror(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        result = check_server("http://localhost:11434")
        assert result is False

    @patch("urllib.request.urlopen")
    def test_returns_false_on_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError()
        result = check_server("http://localhost:11434")
        assert result is False

    @patch("urllib.request.urlopen")
    def test_returns_false_on_oserror(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("Network error")
        result = check_server("http://localhost:11434")
        assert result is False


class TestGetModels:
    """Test get_models function."""

    @patch("urllib.request.urlopen")
    def test_returns_models_list(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"models": [{"name": "qwen2.5:7b"}, {"name": "llama3:8b"}]}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = get_models("http://localhost:11434")
        assert len(result) == 2
        assert result[0]["name"] == "qwen2.5:7b"
        assert result[1]["name"] == "llama3:8b"

    @patch("urllib.request.urlopen")
    def test_returns_empty_when_no_models_key(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = get_models("http://localhost:11434")
        assert result == []


class TestDiscoverOllama:
    """Test discover_ollama function."""

    @patch("agent.ollama.discovery.find_ollama_binary", return_value="/usr/bin/ollama")
    @patch("agent.ollama.discovery.get_ollama_host", return_value="http://localhost:11434")
    @patch("agent.ollama.discovery.check_server", return_value=False)
    def test_returns_installed_when_server_down(self, mock_check, mock_host, mock_binary):
        result = discover_ollama()
        assert result["installed"] is True
        assert result["binary"] == "/usr/bin/ollama"
        assert result["host"] == "http://localhost:11434"
        assert result["running"] is False
        assert result["models"] == []

    @patch("agent.ollama.discovery.find_ollama_binary", return_value=None)
    @patch("agent.ollama.discovery.get_ollama_host", return_value="http://localhost:11434")
    @patch("agent.ollama.discovery.check_server", return_value=False)
    def test_returns_not_installed_when_binary_missing(self, mock_check, mock_host, mock_binary):
        result = discover_ollama()
        assert result["installed"] is False
        assert result["binary"] is None
        assert result["running"] is False
        assert result["models"] == []

    @patch("agent.ollama.discovery.find_ollama_binary", return_value="/usr/bin/ollama")
    @patch("agent.ollama.discovery.get_ollama_host", return_value="http://localhost:11434")
    @patch("agent.ollama.discovery.check_server", return_value=True)
    @patch("agent.ollama.discovery.get_models", return_value=[{"name": "qwen2.5:7b"}])
    def test_returns_models_when_server_up(self, mock_get_models, mock_check, mock_host, mock_binary):
        result = discover_ollama()
        assert result["installed"] is True
        assert result["running"] is True
        assert result["models"] == [{"name": "qwen2.5:7b"}]

    @patch("agent.ollama.discovery.find_ollama_binary", return_value="/usr/bin/ollama")
    @patch("agent.ollama.discovery.get_ollama_host", return_value="http://localhost:11434")
    @patch("agent.ollama.discovery.check_server", return_value=True)
    @patch("agent.ollama.discovery.get_models", side_effect=Exception("API error"))
    def test_handles_get_models_exception(self, mock_get_models, mock_check, mock_host, mock_binary):
        result = discover_ollama()
        assert result["running"] is True
        assert result["models"] == []