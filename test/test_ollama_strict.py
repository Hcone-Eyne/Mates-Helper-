"""Focused tests for Ollama exact-model selection (P1-9).

A configured-but-missing model must never be silently swapped: non-strict
mode warns on stderr naming both models, strict mode (argument or
OLLAMA_STRICT_MODEL) raises naming the missing model. Covers both the
client and the conversation manager, which used to substitute silently on
its own path. Ollama is always mocked - no daemon required.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.ollama.client import OllamaClient


def _info(*names):
    return {
        "installed": True,
        "binary": "ollama",
        "host": "http://127.0.0.1:11434",
        "running": True,
        "models": [{"name": name} for name in names],
    }


@pytest.fixture()
def discover(monkeypatch):
    """Patch discovery in BOTH namespaces that resolve models."""
    from agent.fox.conversation import manager as manager_module

    def _patch(info):
        monkeypatch.setattr("agent.ollama.client.discover_ollama", lambda: info)
        monkeypatch.setattr(manager_module, "discover_ollama", lambda: info)

    return _patch


@pytest.fixture()
def manager_class():
    from agent.fox.conversation.manager import FoxConversationManager

    return FoxConversationManager


class TestExactModelUsed:
    def test_available_model_is_used_verbatim(self, discover):
        discover(_info("qwen3:4b"))
        assert OllamaClient(model="qwen3:4b").model == "qwen3:4b"

    def test_manager_preserves_configured_model(self, discover, manager_class):
        discover(_info("qwen3:4b"))
        manager = manager_class(model="qwen3:4b")
        assert manager.model == "qwen3:4b"
        assert manager.client.model == "qwen3:4b"


class TestStrictMode:
    def test_strict_argument_fails_on_missing_model(self, discover):
        discover(_info("qwen2.5:3b"))
        with pytest.raises(RuntimeError, match="qwen3:4b"):
            OllamaClient(model="qwen3:4b", strict=True)

    def test_strict_env_fails_on_missing_model(self, discover, monkeypatch):
        discover(_info("qwen2.5:3b"))
        monkeypatch.setenv("OLLAMA_STRICT_MODEL", "true")
        with pytest.raises(RuntimeError, match="qwen3:4b"):
            OllamaClient(model="qwen3:4b")

    def test_manager_strict_argument_fails(self, discover, manager_class):
        discover(_info("qwen2.5:3b"))
        with pytest.raises(RuntimeError, match="qwen3:4b"):
            manager_class(model="qwen3:4b", strict=True)

    def test_manager_strict_env_fails(self, discover, manager_class, monkeypatch):
        discover(_info("qwen2.5:3b"))
        monkeypatch.setenv("OLLAMA_STRICT_MODEL", "1")
        with pytest.raises(RuntimeError, match="qwen3:4b"):
            manager_class(model="qwen3:4b")

    def test_strict_error_names_installed_models(self, discover):
        discover(_info("qwen2.5:3b"))
        with pytest.raises(RuntimeError, match="qwen2.5:3b"):
            OllamaClient(model="qwen3:4b", strict=True)


class TestNonStrictFallbackIsObservable:
    def test_fallback_warns_naming_both_models(self, discover, capsys, monkeypatch):
        discover(_info("qwen2.5:3b"))
        monkeypatch.delenv("OLLAMA_STRICT_MODEL", raising=False)
        assert OllamaClient(model="qwen3:4b").model == "qwen2.5:3b"
        err = capsys.readouterr().err
        assert "qwen3:4b" in err and "qwen2.5:3b" in err

    def test_manager_fallback_warns_naming_both_models(
        self, discover, manager_class, capsys, monkeypatch
    ):
        discover(_info("qwen2.5:3b"))
        monkeypatch.delenv("OLLAMA_STRICT_MODEL", raising=False)
        manager = manager_class(model="qwen3:4b")
        assert manager.model == "qwen2.5:3b"
        assert manager.client.model == "qwen2.5:3b"
        err = capsys.readouterr().err
        assert "qwen3:4b" in err and "qwen2.5:3b" in err


class TestStrictParsing:
    @pytest.mark.parametrize("value", ["1", "true", "yes", "on", "True", " YES ", "On"])
    def test_truthy_values_enable_strict(self, discover, monkeypatch, value):
        discover(_info("qwen2.5:3b"))
        monkeypatch.setenv("OLLAMA_STRICT_MODEL", value)
        with pytest.raises(RuntimeError, match="qwen3:4b"):
            OllamaClient(model="qwen3:4b")

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "strict"])
    def test_other_values_do_not_enable_strict(
        self, discover, monkeypatch, capsys, value
    ):
        discover(_info("qwen2.5:3b"))
        monkeypatch.setenv("OLLAMA_STRICT_MODEL", value)
        assert OllamaClient(model="qwen3:4b").model == "qwen2.5:3b"
        assert "falling back" in capsys.readouterr().err


class TestMalformedAndUnreachable:
    def test_missing_models_key_fails_safely(self, monkeypatch):
        info = {"installed": True, "binary": "ollama",
                "host": "http://127.0.0.1:11434", "running": True}
        monkeypatch.setattr("agent.ollama.client.discover_ollama", lambda: info)
        with pytest.raises(RuntimeError, match="No Ollama model"):
            OllamaClient(model="qwen3:4b", strict=True)

    def test_null_models_fails_safely(self, monkeypatch):
        info = {"installed": True, "binary": "ollama",
                "host": "http://127.0.0.1:11434", "running": True, "models": None}
        monkeypatch.setattr("agent.ollama.client.discover_ollama", lambda: info)
        # must be the explicit "no model" error, never a TypeError
        with pytest.raises(RuntimeError, match="No Ollama model"):
            OllamaClient(model="qwen3:4b", strict=True)

    def test_non_dict_entries_fails_safely(self, monkeypatch):
        info = {"installed": True, "binary": "ollama",
                "host": "http://127.0.0.1:11434", "running": True,
                "models": ["qwen3:4b", None, 42, {}]}
        monkeypatch.setattr("agent.ollama.client.discover_ollama", lambda: info)
        with pytest.raises(RuntimeError, match="No Ollama model"):
            OllamaClient(model="qwen3:4b", strict=True)

    def test_unreachable_daemon_with_explicit_model_fails(self, monkeypatch):
        info = {"installed": False, "binary": None,
                "host": "http://127.0.0.1:11434", "running": False, "models": []}
        monkeypatch.setattr("agent.ollama.client.discover_ollama", lambda: info)
        with pytest.raises(RuntimeError, match="No Ollama model"):
            OllamaClient(model="qwen3:4b", strict=True)

    def test_unreachable_daemon_auto_select_fails(self, monkeypatch):
        info = {"installed": False, "binary": None,
                "host": "http://127.0.0.1:11434", "running": False, "models": []}
        monkeypatch.setattr("agent.ollama.client.discover_ollama", lambda: info)
        with pytest.raises(RuntimeError, match="No Ollama model"):
            OllamaClient()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
