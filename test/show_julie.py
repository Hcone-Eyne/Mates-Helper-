#!/usr/bin/env python3

"""Run Julie interactively with the locally configured Ollama model."""

import sys
from pathlib import Path

# Add the repository root so this script works when launched from test/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.julie.julie import Julie, JulieResult, OllamaReasoningBackend
from agent.ollama.client import OllamaClient


def main():
    # Create the Ollama client and show connection errors without a traceback.
    try:
        client = OllamaClient()
    except (RuntimeError, OSError) as exc:
        print(f"[show_julie] Could not initialize Ollama: {exc}", file=sys.stderr)
        return 1

    backend = OllamaReasoningBackend(client)
    julie = Julie(backend)

    try:
        user_input = input("\n🦊 Fox → Julie: ")
    except (EOFError, KeyboardInterrupt):
        print("\n[show_julie] Input cancelled.", file=sys.stderr)
        return 1

    if not user_input.strip():
        print("[show_julie] Please enter a task.", file=sys.stderr)
        return 1

    result = julie.reason(user_input)

    if not isinstance(result, JulieResult):
        print("[show_julie] Julie returned no reasoning result.", file=sys.stderr)
        return 1

    print("\n" + "=" * 60)
    print("🧠 JULIE REASONING")
    print("=" * 60)

    print("\n📌 Expanded Task:")
    print(result.expanded_task)

    print("\n📋 Plan:")
    for i, step in enumerate(result.plan, 1):
        print(f"  {i}. {step}")

    print("\n⚠️ Uncertainty:")
    if result.uncertainty:
        for item in result.uncertainty:
            print(f"  - {item}")
    else:
        print("  None")

    print("\n🤖 Raw Ollama Response:")
    print(result.raw_response)

    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
