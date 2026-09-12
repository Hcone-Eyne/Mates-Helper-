"""
Fox Club Pipeline Test
======================
Test all fox club members when giving a prompt to Fox.

Architecture:
    USER -> FOX -> JULIE -> SELINA -> GWEN -> FOX -> USER

This test simulates the full pipeline with fake backends and executor.
Runtime is NOT wired yet, so we manually connect the agents.

Run: python test.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from agent.julie.julie import Julie, JulieResult
from agent.selina.selina import Selina, SelinaResult
from agent.gwen.gwen import Gwen, GwenResult
from agent.fox.fox import Fox


# ============================================================
# FAKE BACKENDS
# ============================================================

class FakeJulieBackend:
    """Simulates Julie's reasoning backend (Ollama)."""

    def __init__(self, response_json: str):
        self.response = response_json
        self.messages = []

    def generate(self, messages):
        self.messages = messages
        return self.response


class FakeGwenBackend:
    """Simulates Gwen's critic backend (Ollama)."""

    def __init__(self, response: str):
        self.response = response
        self.messages = []

    def generate(self, messages):
        self.messages = messages
        return self.response


class FakeExecutor:
    """Simulates Selina's action executor."""

    def __init__(self, result="executed"):
        self.result = result
        self.calls = []

    def execute(self, action, arguments):
        self.calls.append({"action": action, "arguments": arguments})
        return self.result


class FailingExecutor:
    """Simulates an executor that fails."""

    def execute(self, action, arguments):
        raise RuntimeError("File not found: config.yaml")


# ============================================================
# PIPELINE SIMULATION
# ============================================================

def build_reasoning_string(julie_result: JulieResult, selina_result: SelinaResult) -> str:
    """Combine Julie and Selina output into a single reasoning string for Gwen."""
    parts = [
        f"User request: {julie_result.user_request}",
        f"Julie expanded task: {julie_result.expanded_task}",
        f"Julie plan: {', '.join(julie_result.plan)}",
        f"Julie uncertainty: {', '.join(julie_result.uncertainty) if julie_result.uncertainty else 'none'}",
        "",
        f"Selina interpretation: {selina_result.interpretation}",
        f"Selina action: {selina_result.action}",
        f"Selina success: {selina_result.success}",
        f"Selina result: {selina_result.result}",
        f"Selina error: {selina_result.error}",
    ]
    return "\n".join(parts)


def run_pipeline(user_input: str, julie_response: str, gwen_response: str,
                 executor_result="executed", executor_fails=False):
    """
    Run the full Fox Club pipeline.

    Returns: (julie_result, selina_result, gwen_result)
    """
    print(f"\n{'='*60}")
    print(f"USER INPUT: {user_input}")
    print(f"{'='*60}")

    # --- FOX receives user input ---
    fox = Fox()
    print(f"\n[FOX] Received user input: {user_input!r}")

    # --- JULIE reasons ---
    julie_backend = FakeJulieBackend(julie_response)
    julie = Julie(julie_backend)
    julie_result = julie.reason(user_input)

    if not isinstance(julie_result, JulieResult):
        print(f"[JULIE] Returned string (empty input): {julie_result!r}")
        return None, None, None

    print(f"\n[JULIE] Reasoning complete:")
    print(f"  Expanded task: {julie_result.expanded_task}")
    print(f"  Plan: {julie_result.plan}")
    print(f"  Uncertainty: {julie_result.uncertainty}")

    # --- SELINA executes ---
    if executor_fails:
        executor = FailingExecutor()
    else:
        executor = FakeExecutor(result=executor_result)

    selina = Selina(executor)
    selina_result = selina.execute(julie_result)

    print(f"\n[SELINA] Execution complete:")
    print(f"  Action: {selina_result.action}")
    print(f"  Success: {selina_result.success}")
    print(f"  Result: {selina_result.result}")
    print(f"  Error: {selina_result.error}")
    print(f"  Interpretation: {selina_result.interpretation}")

    # --- GWEN reviews ---
    reasoning = build_reasoning_string(julie_result, selina_result)
    gwen_backend = FakeGwenBackend(gwen_response)
    gwen = Gwen(gwen_backend)
    gwen_result = gwen.review(julie_result.user_request, reasoning)

    print(f"\n[GWEN] Review complete:")
    print(f"  Approved: {gwen_result.approved}")
    print(f"  Critique: {gwen_result.critique}")

    # --- FOX returns to user ---
    print(f"\n[FOX] Returning result to user")

    # Show what Gwen's backend received
    print(f"\n[DEBUG] Gwen's backend received:")
    for i, msg in enumerate(gwen_backend.messages):
        print(f"  Message {i} ({msg['role']}):")
        for line in msg['content'].split('\n'):
            print(f"    {line}")

    return julie_result, selina_result, gwen_result


# ============================================================
# TEST CASES
# ============================================================

def test_success():
    """Test 1: Successful execution, Gwen approves."""
    print("\n" + "#"*60)
    print("# TEST 1: SUCCESSFUL EXECUTION")
    print("#"*60)

    julie_result, selina_result, gwen_result = run_pipeline(
        user_input="read the config file",
        julie_response='{"expanded_task":"Read and return config.yaml","plan":["read_file","parse_yaml"],"uncertainty":["file might not exist"]}',
        gwen_response="APPROVED: true\nCRITIQUE: Execution matches the plan. File was read successfully.",
        executor_result={"key": "value", "debug": True},
    )

    assert julie_result is not None
    assert julie_result.expanded_task == "Read and return config.yaml"
    assert julie_result.plan == ["read_file", "parse_yaml"]

    assert selina_result.success is True
    assert selina_result.action == "read_file"
    assert selina_result.result == {"key": "value", "debug": True}

    assert gwen_result.approved is True
    assert "matches the plan" in gwen_result.critique

    print("\n✅ TEST 1 PASSED")


def test_failure_at_selina():
    """Test 2: Selina's executor fails, Gwen rejects."""
    print("\n" + "#"*60)
    print("# TEST 2: SELINA EXECUTOR FAILURE")
    print("#"*60)

    julie_result, selina_result, gwen_result = run_pipeline(
        user_input="read the config file",
        julie_response='{"expanded_task":"Read config.yaml","plan":["read_file"],"uncertainty":[]}',
        gwen_response="APPROVED: false\nCRITIQUE: Selina failed to execute the action. Executor error.",
        executor_fails=True,
    )

    assert julie_result is not None
    assert selina_result.success is False
    assert "File not found" in selina_result.error
    assert gwen_result.approved is False

    print("\n✅ TEST 2 PASSED")


def test_bad_reasoning():
    """Test 3: Julie's plan is dangerous, Gwen rejects."""
    print("\n" + "#"*60)
    print("# TEST 3: DANGEROUS PLAN REJECTED BY GWEN")
    print("#"*60)

    julie_result, selina_result, gwen_result = run_pipeline(
        user_input="clean up old files",
        julie_response='{"expanded_task":"Delete all old files","plan":["rm -rf /"],"uncertainty":["destructive command"]}',
        gwen_response="APPROVED: false\nCRITIQUE: Dangerous command detected. rm -rf / would destroy the entire filesystem.",
        executor_result="deleted",
    )

    assert julie_result is not None
    assert julie_result.plan == ["rm -rf /"]
    assert gwen_result.approved is False
    assert "dangerous" in gwen_result.critique.lower()

    print("\n✅ TEST 3 PASSED")


def test_no_uncertainty():
    """Test 4: Clear task with no uncertainty."""
    print("\n" + "#"*60)
    print("# TEST 4: CLEAR TASK, NO UNCERTAINTY")
    print("#"*60)

    julie_result, selina_result, gwen_result = run_pipeline(
        user_input="list files in current directory",
        julie_response='{"expanded_task":"List all files in the current directory","plan":["list_directory"],"uncertainty":[]}',
        gwen_response="APPROVED: true\nCRITIQUE: Simple and clear execution.",
        executor_result=["file1.txt", "file2.py", "README.md"],
    )

    assert julie_result is not None
    assert julie_result.uncertainty == []
    assert selina_result.success is True
    assert selina_result.result == ["file1.txt", "file2.py", "README.md"]
    assert gwen_result.approved is True

    print("\n✅ TEST 4 PASSED")


def test_with_context():
    """Test 5: Julie receives context along with user request."""
    print("\n" + "#"*60)
    print("# TEST 5: JULIE WITH CONTEXT")
    print("#"*60)

    julie_backend = FakeJulieBackend(
        '{"expanded_task":"Deploy the app to production","plan":["build","push","restart"],"uncertainty":["might need rollback"]}'
    )
    julie = Julie(julie_backend)
    julie_result = julie.reason("deploy the app", "user is in production environment")

    print(f"\n[JULIE] Context received: {julie_result.context}")
    assert julie_result.context == "user is in production environment"
    assert julie_result.user_request == "deploy the app"

    executor = FakeExecutor(result="deployed")
    selina = Selina(executor)
    selina_result = selina.execute(julie_result)

    reasoning = build_reasoning_string(julie_result, selina_result)
    gwen_backend = FakeGwenBackend("APPROVED: true\nCRITIQUE: Deployment completed successfully.")
    gwen = Gwen(gwen_backend)
    gwen_result = gwen.review(julie_result.user_request, reasoning)

    assert gwen_result.approved is True
    print("\n✅ TEST 5 PASSED")


def test_empty_input():
    """Test 6: Empty input handled gracefully."""
    print("\n" + "#"*60)
    print("# TEST 6: EMPTY INPUT")
    print("#"*60)

    julie_backend = FakeJulieBackend("should not be called")
    julie = Julie(julie_backend)
    julie_result = julie.reason("")

    print(f"[JULIE] Empty input returns: {type(julie_result).__name__} = {julie_result!r}")
    assert julie_result == ""
    print("\n✅ TEST 6 PASSED")


def test_result_immutability():
    """Test 7: Results are frozen (immutable)."""
    print("\n" + "#"*60)
    print("# TEST 7: RESULT IMMUTABILITY")
    print("#"*60)

    julie_result, selina_result, gwen_result = run_pipeline(
        user_input="test immutability",
        julie_response='{"expanded_task":"Test","plan":["step"],"uncertainty":[]}',
        gwen_response="APPROVED: true\nCRITIQUE: OK",
        executor_result="done",
    )

    # Test JulieResult is frozen
    try:
        julie_result.expanded_task = "changed"
        print("❌ JulieResult is mutable (should be frozen)")
        assert False
    except AttributeError:
        print("[JULIE] JulieResult is frozen: OK")

    # Test SelinaResult is frozen
    try:
        selina_result.success = False
        print("❌ SelinaResult is mutable (should be frozen)")
        assert False
    except AttributeError:
        print("[SELINA] SelinaResult is frozen: OK")

    # Test GwenResult is frozen
    try:
        gwen_result.approved = False
        print("❌ GwenResult is mutable (should be frozen)")
        assert False
    except AttributeError:
        print("[GWEN] GwenResult is frozen: OK")

    print("\n✅ TEST 7 PASSED")


def test_gwen_reviews_both():
    """Test 8: Gwen's prompt now says she reviews both Julie and Selina."""
    print("\n" + "#"*60)
    print("# TEST 8: GWEN REVIEWS BOTH JULIE AND SELINA")
    print("#"*60)

    prompt = Gwen.SYSTEM_PROMPT
    assert "Julie" in prompt
    assert "Selina" in prompt
    assert "both" in prompt.lower() or "Julie's reasoning and Selina's execution" in prompt

    print("[GWEN] System prompt mentions reviewing both Julie and Selina: OK")
    print(f"  Key phrase: 'Julie's reasoning and Selina's execution' in prompt: ", end="")
    print("YES" if "Julie's reasoning and Selina's execution" in prompt else "NO")

    print("\n✅ TEST 8 PASSED")


def test_data_flow_complete():
    """Test 9: All data flows correctly through the pipeline."""
    print("\n" + "#"*60)
    print("# TEST 9: COMPLETE DATA FLOW")
    print("#"*60)

    julie_result, selina_result, gwen_result = run_pipeline(
        user_input="specific user request text",
        julie_response='{"expanded_task":"Specific task description","plan":["step_a","step_b","step_c"],"uncertainty":["unclear part"]}',
        gwen_response="APPROVED: true\nCRITIQUE: All data preserved.",
        executor_result={"specific": "result"},
    )

    # Julie data preserved
    assert julie_result.user_request == "specific user request text"
    assert julie_result.expanded_task == "Specific task description"
    assert julie_result.plan == ["step_a", "step_b", "step_c"]
    assert julie_result.uncertainty == ["unclear part"]
    print("[DATA] Julie data preserved: OK")

    # Selina data preserved
    assert selina_result.expanded_task == "Specific task description"
    assert selina_result.action == "step_a"
    assert selina_result.result == {"specific": "result"}
    assert selina_result.error is None
    print("[DATA] Selina data preserved: OK")

    # Gwen received both
    gwen_content = gwen_result.reasoning
    assert "Specific task description" in gwen_content
    assert "step_a" in gwen_content
    assert "step_b" in gwen_content
    assert "step_c" in gwen_content
    assert "unclear part" in gwen_content
    assert "Selina" in gwen_content
    print("[DATA] Gwen received Julie and Selina data: OK")

    print("\n✅ TEST 9 PASSED")


def test_fox_input_validation():
    """Test 10: Fox validates input correctly."""
    print("\n" + "#"*60)
    print("# TEST 10: FOX INPUT VALIDATION")
    print("#"*60)

    fox = Fox()

    # Test non-string input
    try:
        fox.ask(123)
        print("❌ Fox should raise TypeError for non-string input")
        assert False
    except TypeError as e:
        print(f"[FOX] Non-string input rejected: {e}")

    # Test empty input
    result = fox.ask("")
    assert result == ""
    print("[FOX] Empty input returns empty string: OK")

    # Test no runtime
    try:
        fox.ask("test")
        print("❌ Fox should raise RuntimeError when no runtime attached")
        assert False
    except RuntimeError as e:
        print(f"[FOX] No runtime attached: {e}")

    print("\n✅ TEST 10 PASSED")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("="*60)
    print("FOX CLUB MEMBER PIPELINE TEST")
    print("="*60)
    print("\nArchitecture: USER -> FOX -> JULIE -> SELINA -> GWEN -> FOX -> USER")
    print("Testing with fake backends and executor (no Ollama required)\n")

    tests = [
        test_success,
        test_failure_at_selina,
        test_bad_reasoning,
        test_no_uncertainty,
        test_with_context,
        test_empty_input,
        test_result_immutability,
        test_gwen_reviews_both,
        test_data_flow_complete,
        test_fox_input_validation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*60)

    if failed == 0:
        print("\n🎉 All Fox Club members are working correctly!")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Check output above.")
        sys.exit(1)
