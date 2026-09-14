"""Optional integration test for Julie with a local Ollama server."""

import os
import sys
from pathlib import Path

import pytest

# Add the repository root when this file is run directly from the test folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.ollama.client import OllamaClient
from agent.julie.julie import Julie, JulieResult, OllamaReasoningBackend


@pytest.mark.skipif(
    os.environ.get("RUN_OLLAMA_TESTS") != "1",
    reason="Set RUN_OLLAMA_TESTS=1 to run the local Ollama integration test.",
)
def test_julie_with_ollama():
    """Verify Julie can parse a structured response from a local Ollama model."""
    try:
        client = OllamaClient(model="qwen2.5:3b-instruct")
    except RuntimeError as exc:
        pytest.skip(f"Ollama is unavailable: {exc}")

    backend = OllamaReasoningBackend(client)
    julie = Julie(backend)

    result = julie.reason(
        "Plan how to organize my Downloads folder."
    )

    assert isinstance(result, JulieResult)
    assert result.user_request == "Plan how to organize my Downloads folder."
    assert result.expanded_task
    assert result.plan
    assert all(isinstance(step, str) and step.strip() for step in result.plan)
    assert all(
        isinstance(item, str) and item.strip()
        for item in result.uncertainty
    )