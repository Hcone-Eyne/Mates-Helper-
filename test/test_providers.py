"""Focused tests for Agent_plugins/providers/ (P1-4).

The openai/openrouter/nvidia modules used to import a nonexistent
`openai_compatible` module. OpenRouter and NVIDIA speak the OpenAI
chat-completions API, so they reuse the existing openai_provider
implementation. All HTTP is mocked - these tests must never call a real
provider API.
"""

import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

requests = pytest.importorskip("requests")

from Agent_plugins.providers import (
    gemini_provider,
    nvidia_provider,
    openai_provider,
    openrouter_provider,
)


def _ok_response(text="hello"):
    response = requests.Response()
    response.status_code = 200
    response._content = (
        b'{"choices": [{"message": {"content": "' + text.encode() + b'"}}]}'
    )
    return response


class TestImports:
    def test_all_provider_modules_import(self):
        for module in (openai_provider, openrouter_provider, nvidia_provider, gemini_provider):
            assert module.__name__.startswith("Agent_plugins.providers.")

    def test_public_signatures_preserved(self):
        assert str(inspect.signature(openai_provider.chat)) == "(prompt, api_key, base_url, model)"
        assert str(inspect.signature(openrouter_provider.chat)) == "(prompt)"
        assert str(inspect.signature(nvidia_provider.chat)) == "(prompt)"


class TestOpenAICompatibleRequest:
    def test_request_construction(self, monkeypatch):
        calls = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            calls.update(url=url, headers=headers, json=json, timeout=timeout)
            return _ok_response()

        monkeypatch.setattr(requests, "post", fake_post)

        assert openai_provider.chat("hi", api_key="k", base_url="https://x.test/v1", model="m") == "hello"
        assert calls["url"] == "https://x.test/v1/chat/completions"
        assert calls["headers"] == {"Authorization": "Bearer k"}
        assert calls["json"] == {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
        assert calls["timeout"] == 60

    def test_http_errors_surface(self, monkeypatch):
        def fake_post(*args, **kwargs):
            raise requests.HTTPError("500 Server Error")

        monkeypatch.setattr(requests, "post", fake_post)

        with pytest.raises(requests.HTTPError):
            openai_provider.chat("hi", api_key="k", base_url="https://x.test/v1", model="m")


class TestOpenRouter:
    def test_request_construction_and_defaults(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
        calls = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            calls.update(url=url, headers=headers, json=json)
            return _ok_response("ro")

        monkeypatch.setattr(requests, "post", fake_post)

        assert openrouter_provider.chat("hi") == "ro"
        assert calls["url"] == "https://openrouter.ai/api/v1/chat/completions"
        assert calls["headers"] == {"Authorization": "Bearer or-key"}
        assert calls["json"]["model"] == "openai/gpt-4o"

    def test_model_override_respected(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        monkeypatch.setenv("OPENROUTER_MODEL", "custom/model")
        seen = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            seen.update(json=json)
            return _ok_response()

        monkeypatch.setattr(requests, "post", fake_post)

        openrouter_provider.chat("hi")
        assert seen["json"]["model"] == "custom/model"

    def test_missing_key_fails_explicitly_before_http(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        called = []
        monkeypatch.setattr(requests, "post", lambda *a, **k: called.append(1))

        with pytest.raises(KeyError):
            openrouter_provider.chat("hi")
        assert called == []


class TestNvidia:
    def test_request_construction_and_defaults(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.delenv("NVIDIA_MODEL", raising=False)
        calls = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            calls.update(url=url, headers=headers, json=json)
            return _ok_response("nv")

        monkeypatch.setattr(requests, "post", fake_post)

        assert nvidia_provider.chat("hi") == "nv"
        assert calls["url"] == "https://integrate.api.nvidia.com/v1/chat/completions"
        assert calls["headers"] == {"Authorization": "Bearer nv-key"}
        assert calls["json"]["model"] == "meta/llama-3.1-70b-instruct"

    def test_model_override_respected(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", "nv-key")
        monkeypatch.setenv("NVIDIA_MODEL", "custom/model")
        seen = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            seen.update(json=json)
            return _ok_response()

        monkeypatch.setattr(requests, "post", fake_post)

        nvidia_provider.chat("hi")
        assert seen["json"]["model"] == "custom/model"

    def test_missing_key_fails_explicitly_before_http(self, monkeypatch):
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
        called = []
        monkeypatch.setattr(requests, "post", lambda *a, **k: called.append(1))

        with pytest.raises(KeyError):
            nvidia_provider.chat("hi")
        assert called == []


class TestFailureClarity:
    @pytest.mark.parametrize("body", [b"{}", b'{"choices": []}'])
    def test_malformed_response_fails_loudly(self, monkeypatch, body):
        response = requests.Response()
        response.status_code = 200
        response._content = body
        monkeypatch.setattr(requests, "post", lambda *a, **k: response)

        # KeyError / IndexError - never a silent wrong answer
        with pytest.raises(Exception):
            openai_provider.chat("hi", api_key="k", base_url="https://x.test/v1", model="m")

    def test_errors_never_contain_the_api_key(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "super-secret-key")

        def fake_post(*args, **kwargs):
            raise requests.HTTPError("500 Server Error")

        monkeypatch.setattr(requests, "post", fake_post)

        with pytest.raises(requests.HTTPError) as exc_info:
            openrouter_provider.chat("hi")
        assert "super-secret-key" not in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
