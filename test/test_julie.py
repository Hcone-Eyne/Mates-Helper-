"""Focused tests for Julie's prompt construction and structured results."""

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


def test_reason_always_sends_user_request_and_interpolates_context():
    backend = RecordingBackend(
        '{"expanded_task":"Do the task","plan":["First"],"uncertainty":[]}'
    )

    result = Julie(backend).reason("  do it  ", "  relevant context  ")

    assert isinstance(result, JulieResult)
    assert result.user_request == "do it"
    assert result.context == "relevant context"
    assert result.expanded_task == "Do the task"
    assert result.plan == ["First"]
    assert result.uncertainty == []
    assert backend.messages[-1] == {"role": "user", "content": "do it"}
    assert backend.messages[-2]["content"] == "Context:\nrelevant context"


def test_reason_sends_user_request_without_context():
    backend = RecordingBackend(
        '{"expanded_task":"Do the task","plan":[],"uncertainty":["Need input"]}'
    )

    result = Julie(backend).reason("do it", None)

    assert isinstance(result, JulieResult)
    assert [message["role"] for message in backend.messages] == ["system", "user"]
    assert result.uncertainty == ["Need input"]


def test_reason_rejects_unstructured_backend_output():
    backend = RecordingBackend("Here is a plan.")

    with pytest.raises(ValueError, match="invalid JSON"):
        Julie(backend).reason("do it", None)


def test_ollama_backend_validates_response_shape():
    class Client:
        def chat(self, messages):
            return {"message": {"content": 123}}

    with pytest.raises(RuntimeError, match="Invalid response"):
        OllamaReasoningBackend(Client()).generate([])
