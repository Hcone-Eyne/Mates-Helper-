"""Configuration, secret and deployment-boundary checks.

Covers the audit findings that are configuration rather than behaviour:
no hardcoded secrets, model/provider settings are configurable, the Ollama
client's silent model fallback is pinned as known behaviour, and the compose
isolation claims (no published ports on the proxy/sandbox, NET_ADMIN only on
the sandbox) cannot regress unnoticed.
"""

import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO_ROOT = Path(__file__).resolve().parent.parent

SECRET_PATTERNS = {
    "anthropic key": r"sk-ant-[A-Za-z0-9]{10,}",
    "nvidia key": r"nvapi-[A-Za-z0-9_-]{10,}",
    "openrouter key": r"sk-or-v1-[A-Za-z0-9]{10,}",
    "gemini key": r"AIza[0-9A-Za-z_-]{20,}",
    "github token": r"ghp_[A-Za-z0-9]{20,}",
    "aws key": r"AKIA[0-9A-Z]{16}",
    "inline api_key literal": r"""api_key\s*=\s*["'][A-Za-z0-9]{16,}["']""",
}


def _source_files():
    for path in REPO_ROOT.rglob("*.py"):
        if {"venv", ".git", "__pycache__", ".venv"} & set(path.parts):
            continue
        yield path


class TestNoHardcodedSecrets:

    @pytest.mark.parametrize("path", list(_source_files()))
    def test_file_has_no_secret(self, path):
        text = path.read_text(errors="ignore")
        for label, pattern in SECRET_PATTERNS.items():
            match = re.search(pattern, text)
            assert match is None, (
                f"{path.relative_to(REPO_ROOT)} looks like it contains a "
                f"{label}: {match.group(0)[:12]}..."
            )

    @pytest.mark.parametrize(
        "relative",
        [
            "Agent_plugins/providers/nvidia_provider.py",
            "Agent_plugins/providers/openrouter_provider.py",
            "Agent_plugins/providers/gemini_provider.py",
        ],
    )
    def test_provider_keys_come_from_environment(self, relative):
        text = (REPO_ROOT / relative).read_text()
        assert "os.environ[" in text or "os.getenv" in text

    def test_anthropic_key_comes_from_environment(self):
        text = (REPO_ROOT / "brain" / "orchestrator.py").read_text()
        assert 'os.getenv("ANTHROPIC_API_KEY")' in text

    def test_env_files_are_ignored(self):
        ignore = (REPO_ROOT / ".gitignore").read_text()
        for entry in (".env", "venv/", ".DS_Store", ".aider*"):
            assert entry in ignore, f".gitignore is missing {entry}"


class TestModelConfiguration:

    def _fake_discover(self, models):
        return {
            "installed": True,
            "binary": "ollama",
            "host": "http://127.0.0.1:11434",
            "models": [{"name": name} for name in models],
        }

    def test_requested_model_is_used_when_available(self):
        from agent.ollama.client import OllamaClient

        info = self._fake_discover(["qwen3:8b", "llama3.2"])
        with patch("agent.ollama.client.discover_ollama", return_value=info):
            assert OllamaClient(model="llama3.2").model == "llama3.2"

    def test_unavailable_model_falls_back_with_an_explicit_warning(
        self, capsys, monkeypatch
    ):
        """Fallback stays the default, but it is no longer silent.

        A caller can now see that the model it asked for is not the model
        that will answer, and can opt into an error via OLLAMA_STRICT_MODEL.
        """
        from agent.ollama.client import OllamaClient

        monkeypatch.delenv("OLLAMA_STRICT_MODEL", raising=False)
        info = self._fake_discover(["qwen3:8b"])
        with patch("agent.ollama.client.discover_ollama", return_value=info):
            assert OllamaClient(model="gpt-4o").model == "qwen3:8b"

        err = capsys.readouterr().err
        assert "gpt-4o" in err, "warning must name the requested model"
        assert "qwen3:8b" in err, "warning must name the substituted model"
        assert "OLLAMA_STRICT_MODEL" in err, "warning must name the escape hatch"

    def test_available_model_produces_no_fallback_warning(self, capsys):
        from agent.ollama.client import OllamaClient

        info = self._fake_discover(["llama3.2"])
        with patch("agent.ollama.client.discover_ollama", return_value=info):
            OllamaClient(model="llama3.2")

        assert capsys.readouterr().err == ""

    def test_strict_env_refuses_to_substitute_a_model(self, monkeypatch):
        from agent.ollama.client import OllamaClient

        monkeypatch.setenv("OLLAMA_STRICT_MODEL", "1")
        info = self._fake_discover(["qwen3:8b"])
        with patch("agent.ollama.client.discover_ollama", return_value=info):
            with pytest.raises(RuntimeError, match="gpt-4o"):
                OllamaClient(model="gpt-4o")

    def test_strict_argument_beats_a_disabled_env(self, monkeypatch):
        from agent.ollama.client import OllamaClient

        monkeypatch.setenv("OLLAMA_STRICT_MODEL", "0")
        info = self._fake_discover(["qwen3:8b"])
        with patch("agent.ollama.client.discover_ollama", return_value=info):
            with pytest.raises(RuntimeError, match="qwen3:8b"):
                OllamaClient(model="gpt-4o", strict=True)

    def test_strict_mode_lists_the_installed_models(self, monkeypatch):
        from agent.ollama.client import OllamaClient

        monkeypatch.setenv("OLLAMA_STRICT_MODEL", "true")
        info = self._fake_discover(["qwen3:4b", "llama3.2"])
        with patch("agent.ollama.client.discover_ollama", return_value=info):
            with pytest.raises(RuntimeError, match="qwen3:4b, llama3.2"):
                OllamaClient(model="gpt-4o")

    def test_ollama_model_env_is_honoured(self):
        from agent.ollama.client import OllamaClient

        info = self._fake_discover(["qwen3:8b", "llama3.2"])
        with patch("agent.ollama.client.discover_ollama", return_value=info):
            with patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.2"}):
                assert OllamaClient().model == "llama3.2"

    def test_ollama_host_is_configurable(self, monkeypatch):
        from agent.ollama.discovery import get_ollama_host

        monkeypatch.delenv("OLLAMA_HOST", raising=False)
        assert get_ollama_host() == "http://127.0.0.1:11434"

        monkeypatch.setenv("OLLAMA_HOST", "http://gpu-box:11434/")
        assert get_ollama_host() == "http://gpu-box:11434"

    def test_agent_endpoint_defaults(self):
        from brain.tools import AGENT_HOST, AGENT_PORT

        assert AGENT_HOST == "agent"
        # port is interpolated into the browse URL, so the string form is fine
        assert str(AGENT_PORT) == "9000"


class TestComposeIsolationBoundary:
    """The compose file is the isolation boundary - pin its shape.

    This is container/network isolation (shared docker network, published
    ports, capability grants), NOT VM-grade security.
    """

    @pytest.fixture
    def compose(self):
        return yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())

    def test_proxy_publishes_no_ports(self, compose):
        assert "ports" not in compose["services"]["mitm-proxy"]

    def test_sandbox_agent_publishes_no_ports(self, compose):
        assert "ports" not in compose["services"]["agent"]

    def test_sandbox_agent_grant_is_net_admin_only(self, compose):
        assert compose["services"]["agent"]["cap_add"] == ["NET_ADMIN"]

    def test_sandbox_agent_cannot_read_proxy_logs(self, compose):
        assert "volumes" not in compose["services"]["agent"]

    def test_agent_traffic_is_proxied(self, compose):
        environment = compose["services"]["agent"]["environment"]
        assert "HTTP_PROXY=http://mitm-proxy:8080" in environment
        assert "HTTPS_PROXY=http://mitm-proxy:8080" in environment

    def test_brain_is_the_only_published_service(self, compose):
        published = {
            name: service.get("ports")
            for name, service in compose["services"].items()
            if service.get("ports")
        }
        assert published == {"brain": ["127.0.0.1:7010:7000"]}

    def test_brain_api_is_loopback_only(self, compose):
        """The brain API has no authentication (and /files/delete is
        destructive), so it must not be reachable from other hosts."""
        assert compose["services"]["brain"]["ports"][0].startswith("127.0.0.1:")

    def test_all_services_share_the_internal_network(self, compose):
        for name, service in compose["services"].items():
            assert service["networks"] == ["sandbox-net"], name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
