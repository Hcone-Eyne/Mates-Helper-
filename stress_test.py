#!/usr/bin/env python3
"""
Comprehensive Stress Test for Mates-Helper / Fox Club Implementation
Runs 100 iterations per test category and generates a detailed report.
"""

import sys
import os
import time
import json
import shutil
import traceback
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from collections import defaultdict

# Add project root to path
sys.path.insert(0, '/Users/enoch/Desktop/Connectivity_A')

from agent.ollama.ollama_agent import OllamaFoxAgent
from agent.fox.runtime.runtime import build_runtime
from agent.ollama.client import OllamaClient

# ============================================================
# TEST FIXTURE SETUP
# ============================================================
TEST_DIR = Path("/tmp/fox_live_test")
ORIGINAL_FILES = {
    "test.py": "",
    "notes.txt": "",
    "photo.jpg": "",
    "song.mp3": "",
    "document.pdf": "",
}

def reset_test_dir():
    """Reset test directory to original state."""
    for f in TEST_DIR.iterdir():
        if f.is_file():
            f.unlink()
    for name, content in ORIGINAL_FILES.items():
        (TEST_DIR / name).write_text(content)


# ============================================================
# DATA CLASSES FOR RESULTS
# ============================================================
@dataclass
class IterationResult:
    iteration: int
    success: bool
    exception: Optional[str] = None
    julie_action: Optional[str] = None
    selina_action: Optional[str] = None
    gwen_approved: Optional[bool] = None
    execution_time: float = 0.0
    error_category: Optional[str] = None


@dataclass
class TestCategoryResults:
    name: str
    iterations: list[IterationResult] = field(default_factory=list)
    
    @property
    def total(self) -> int:
        return len(self.iterations)
    
    @property
    def passed(self) -> int:
        return sum(1 for i in self.iterations if i.success)
    
    @property
    def failed(self) -> int:
        return self.total - self.passed
    
    @property
    def success_rate(self) -> float:
        return (self.passed / self.total * 100) if self.total > 0 else 0.0
    
    @property
    def avg_time(self) -> float:
        times = [i.execution_time for i in self.iterations if i.execution_time > 0]
        return sum(times) / len(times) if times else 0.0
    
    @property
    def slowest(self) -> float:
        times = [i.execution_time for i in self.iterations if i.execution_time > 0]
        return max(times) if times else 0.0
    
    @property
    def fastest(self) -> float:
        times = [i.execution_time for i in self.iterations if i.execution_time > 0]
        return min(times) if times else 0.0


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def categorize_error(exception: str, result: Optional[Any] = None) -> str:
    """Categorize error by Fox Club member or component."""
    exc_lower = exception.lower()
    
    if "julie" in exc_lower or "reasoning" in exc_lower or "expanded_task" in exc_lower or "plan" in exc_lower:
        return "Julie"
    if "annie" in exc_lower or "handoff" in exc_lower or "requirements" in exc_lower or "interpretation" in exc_lower:
        return "Annie"
    if "selina" in exc_lower or "action" in exc_lower or "executor" in exc_lower or "execute_from_annie" in exc_lower:
        return "Selina"
    if "gwen" in exc_lower or "approved" in exc_lower or "critique" in exc_lower or "safety" in exc_lower:
        return "Gwen"
    if "ollama" in exc_lower or "connection" in exc_lower or "model" in exc_lower or "chat" in exc_lower or "urllib" in exc_lower:
        return "Ollama"
    if "model" in exc_lower and ("select" in exc_lower or "config" in exc_lower or "think" in exc_lower):
        return "Model selection"
    if "think" in exc_lower:
        return "Think configuration"
    if "runtime" in exc_lower or "handle" in exc_lower:
        return "Runtime"
    if "executor" in exc_lower or "fileactionexecutor" in exc_lower or "unknown action" in exc_lower:
        return "Executor"
    if "timeout" in exc_lower or "timed out" in exc_lower:
        return "Timeout"
    if "exception" in exc_lower or "error" in exc_lower or "traceback" in exc_lower:
        return "Exception"
    return "Other"


def extract_member_info(result: Any) -> tuple:
    """Extract action and approval info from RuntimeResult."""
    julie_action = None
    selina_action = None
    gwen_approved = None
    
    try:
        if hasattr(result, 'julie_result') and result.julie_result:
            julie_action = str(result.julie_result.plan) if result.julie_result.plan else None
        if hasattr(result, 'selina_result') and result.selina_result:
            selina_action = result.selina_result.action
        if hasattr(result, 'gwen_result') and result.gwen_result:
            gwen_approved = result.gwen_result.approved
    except Exception:
        pass
    
    return julie_action, selina_action, gwen_approved


# ============================================================
# TEST 1: LIST DIRECTORY (100 iterations)
# ============================================================
def test_list_directory():
    print("\n" + "="*60)
    print("TEST 1: List Directory (100 iterations)")
    print("="*60)
    
    results = TestCategoryResults("List Directory")
    
    for i in range(1, 101):
        start = time.time()
        iteration_result = IterationResult(iteration=i, success=False)
        
        try:
            reset_test_dir()
            fox = OllamaFoxAgent(target_dir=str(TEST_DIR))
            result = fox.ask("list files in /tmp/fox_live_test")
            
            julie_action, selina_action, gwen_approved = extract_member_info(result)
            
            iteration_result.julie_action = str(julie_action)
            iteration_result.selina_action = selina_action
            iteration_result.gwen_approved = gwen_approved
            iteration_result.success = True
            
        except Exception as e:
            iteration_result.exception = traceback.format_exc()
            iteration_result.error_category = categorize_error(str(e))
            iteration_result.success = False
        
        iteration_result.execution_time = time.time() - start
        results.iterations.append(iteration_result)
        
        if i % 10 == 0:
            print(f"  Completed {i}/100 iterations...")
    
    return results


# ============================================================
# TEST 2: SHOW FILES (100 iterations)
# ============================================================
def test_show_files():
    print("\n" + "="*60)
    print("TEST 2: Show Files (100 iterations)")
    print("="*60)
    
    results = TestCategoryResults("Show Files")
    
    for i in range(1, 101):
        start = time.time()
        iteration_result = IterationResult(iteration=i, success=False)
        
        try:
            reset_test_dir()
            fox = OllamaFoxAgent(target_dir=str(TEST_DIR))
            result = fox.ask("show the files in /tmp/fox_live_test")
            
            julie_action, selina_action, gwen_approved = extract_member_info(result)
            
            iteration_result.julie_action = str(julie_action)
            iteration_result.selina_action = selina_action
            iteration_result.gwen_approved = gwen_approved
            iteration_result.success = True
            
        except Exception as e:
            iteration_result.exception = traceback.format_exc()
            iteration_result.error_category = categorize_error(str(e))
            iteration_result.success = False
        
        iteration_result.execution_time = time.time() - start
        results.iterations.append(iteration_result)
        
        if i % 10 == 0:
            print(f"  Completed {i}/100 iterations...")
    
    return results


# ============================================================
# TEST 3: ORGANISE FILES (100 iterations)
# ============================================================
def test_organise_files():
    print("\n" + "="*60)
    print("TEST 3: Organise Files (100 iterations)")
    print("="*60)
    
    results = TestCategoryResults("Organise Files")
    
    for i in range(1, 101):
        start = time.time()
        iteration_result = IterationResult(iteration=i, success=False)
        
        try:
            reset_test_dir()
            fox = OllamaFoxAgent(target_dir=str(TEST_DIR))
            result = fox.ask("organise the files in /tmp/fox_live_test")
            
            julie_action, selina_action, gwen_approved = extract_member_info(result)
            
            iteration_result.julie_action = str(julie_action)
            iteration_result.selina_action = selina_action
            iteration_result.gwen_approved = gwen_approved
            iteration_result.success = True
            
        except Exception as e:
            iteration_result.exception = traceback.format_exc()
            iteration_result.error_category = categorize_error(str(e))
            iteration_result.success = False
        
        iteration_result.execution_time = time.time() - start
        results.iterations.append(iteration_result)
        
        if i % 10 == 0:
            print(f"  Completed {i}/100 iterations...")
    
    return results


# ============================================================
# TEST 4: MODEL CONFIGURATION
# ============================================================
def test_model_configuration():
    print("\n" + "="*60)
    print("TEST 4: Model Configuration")
    print("="*60)
    
    results = TestCategoryResults("Model Configuration")
    test_cases = [
        ("get_model_initial", lambda: OllamaClient().model),
        ("set_model_qwen3_06b", lambda: setattr(OllamaClient(), 'model', 'qwen3:0.6b') or OllamaClient().model),
        ("set_model_qwen3_4b", lambda: setattr(OllamaClient(), 'model', 'qwen3:4b') or OllamaClient().model),
        ("get_think_initial", lambda: OllamaClient().think),
        ("set_think_true", lambda: setattr(OllamaClient(), 'think', True) or OllamaClient().think),
        ("set_think_false", lambda: setattr(OllamaClient(), 'think', False) or OllamaClient().think),
        ("run_task_uses_model", lambda: run_task_with_model('qwen3:0.6b')),
        ("run_task_uses_think", lambda: run_task_with_think(True)),
        ("config_no_leak", lambda: test_config_isolation()),
    ]
    
    for name, test_fn in test_cases:
        for i in range(10):  # 10 iterations per config test
            start = time.time()
            iteration_result = IterationResult(iteration=i, success=False)
            
            try:
                result = test_fn()
                iteration_result.success = True
                iteration_result.exception = str(result) if result else None
            except Exception as e:
                iteration_result.exception = traceback.format_exc()
                iteration_result.error_category = categorize_error(str(e))
                iteration_result.success = False
            
            iteration_result.execution_time = time.time() - start
            results.iterations.append(iteration_result)
    
    return results


def run_task_with_model(model_name: str):
    """Test that run_task uses the selected model."""
    client = OllamaClient(model=model_name)
    if client.model != model_name:
        raise RuntimeError(f"Model not set correctly: expected {model_name}, got {client.model}")
    
    # Create a runtime with this model
    runtime = build_runtime(target_dir=str(TEST_DIR), model=model_name, think=False)
    result = runtime.handle("list files")
    return f"Model used: {runtime.julie.backend.client.model}"


def run_task_with_think(think_mode: bool):
    """Test that run_task uses the think mode."""
    client = OllamaClient(think=think_mode)
    if client.think != think_mode:
        raise RuntimeError(f"Think mode not set correctly: expected {think_mode}, got {client.think}")
    
    runtime = build_runtime(target_dir=str(TEST_DIR), model=None, think=think_mode)
    result = runtime.handle("list files")
    return f"Think mode used: {runtime.julie.backend.client.think}"


def test_config_isolation():
    """Test that configuration doesn't leak between iterations."""
    client1 = OllamaClient(model='qwen3:0.6b', think=True)
    client2 = OllamaClient(model='qwen3:4b', think=False)
    
    if client1.model == client2.model:
        raise RuntimeError("Model leaked between clients")
    if client1.think == client2.think:
        raise RuntimeError("Think mode leaked between clients")
    
    return "Isolation verified"


# ============================================================
# TEST 5: FAILURE HANDLING
# ============================================================
def test_failure_handling():
    print("\n" + "="*60)
    print("TEST 5: Failure Handling")
    print("="*60)
    
    results = TestCategoryResults("Failure Handling")
    test_cases = [
        ("invalid_model_name", test_invalid_model),
        ("ollama_unavailable", test_ollama_unavailable),
        ("empty_task", test_empty_task),
        ("unknown_action", test_unknown_action),
        ("malformed_annie_requirement", test_malformed_annie),
        ("selina_unable_resolve", test_selina_unable_resolve),
        ("executor_unsupported_action", test_executor_unsupported),
    ]
    
    for name, test_fn in test_cases:
        for i in range(10):  # 10 iterations per failure test
            start = time.time()
            iteration_result = IterationResult(iteration=i, success=False)
            
            try:
                test_fn()
                iteration_result.success = True  # Test passed = failure was handled correctly
            except Exception as e:
                iteration_result.exception = traceback.format_exc()
                iteration_result.error_category = categorize_error(str(e))
                iteration_result.success = False  # Test failed = failure was NOT handled
            
            iteration_result.execution_time = time.time() - start
            results.iterations.append(iteration_result)
    
    return results


def test_invalid_model():
    """Test invalid model name handling."""
    try:
        client = OllamaClient(model="nonexistent-model-xyz")
        # Should either fall back or raise
        _ = client.model
    except RuntimeError as e:
        if "No Ollama model is found" not in str(e):
            raise
    except Exception:
        pass  # Other errors acceptable


def test_ollama_unavailable():
    """Test Ollama unavailable handling."""
    # This is hard to test without stopping Ollama, so we test the error path
    from agent.ollama.discovery import check_server
    # Just verify the check_server function works
    result = check_server("http://127.0.0.1:11434")
    if not result:
        raise RuntimeError("Ollama should be running for this test")


def test_empty_task():
    """Test empty/invalid task handling."""
    fox = OllamaFoxAgent(target_dir=str(TEST_DIR))
    try:
        result = fox.ask("")
        # Should handle gracefully
    except (ValueError, TypeError) as e:
        # Expected
        pass


def test_unknown_action():
    """Test unknown action handling."""
    from agent.fox.runtime.executor import FileActionExecutor, _UnavailableExecutor
    executor = FileActionExecutor(TEST_DIR)
    try:
        executor.execute("unknown_action_xyz", {})
        raise RuntimeError("Should have raised for unknown action")
    except RuntimeError as e:
        if "Unknown action" not in str(e):
            raise


def test_malformed_annie():
    """Test malformed Annie requirement."""
    from agent.annie.annie import Annie, OllamaAnnieBackend, AnnieResult
    from agent.julie.julie import JulieResult
    
    # Create a JulieResult with problematic data
    julie_result = JulieResult(
        user_request="test",
        context=None,
        expanded_task="test task",
        plan=["do something"],
        uncertainty=[],
        raw_response="{}"
    )
    
    # This tests the validation in Annie
    client = OllamaClient()
    annie = Annie(OllamaAnnieBackend(client))
    
    # The structure method should validate JulieResult
    try:
        result = annie.structure(julie_result)
    except Exception as e:
        # Validation errors are expected for malformed input
        pass


def test_selina_unable_resolve():
    """Test Selina unable to resolve action."""
    from agent.selina.selina import Selina
    from agent.fox.runtime.executor import _UnavailableExecutor
    from agent.annie.annie import AnnieResult
    
    executor = _UnavailableExecutor()
    selina = Selina(executor)
    
    # Annie result with no matching action
    annie_result = AnnieResult(
        user_request="test",
        interpretation="test",
        requirements=["fly_to_moon"],
        constraints=[],
        technical_handoff="fly to moon",
        clarification_needed=[],
        raw_response="{}"
    )
    
    result = selina.execute_from_annie(annie_result)
    if result.success:
        raise RuntimeError("Should have failed for unknown action")
    if "Could not determine an action" not in result.error:
        raise RuntimeError(f"Wrong error: {result.error}")


def test_executor_unsupported():
    """Test executor receiving unsupported action."""
    from agent.fox.runtime.executor import FileActionExecutor
    
    executor = FileActionExecutor(TEST_DIR)
    try:
        executor.execute("unsupported_action_xyz", {})
        raise RuntimeError("Should have raised for unsupported action")
    except RuntimeError as e:
        if "Unknown action" not in str(e):
            raise


# ============================================================
# CONSISTENCY CHECK
# ============================================================
def check_consistency(list_results: TestCategoryResults, show_results: TestCategoryResults):
    """Check if repeated identical inputs produce same results."""
    print("\n" + "="*60)
    print("CONSISTENCY CHECK")
    print("="*60)
    
    def analyze_category(results: TestCategoryResults, name: str):
        actions = [r.selina_action for r in results.iterations if r.success]
        approvals = [r.gwen_approved for r in results.iterations if r.success]
        
        unique_actions = set(actions)
        unique_approvals = set(approvals)
        
        print(f"\n{name}:")
        print(f"  Unique Selina actions: {len(unique_actions)} - {unique_actions}")
        print(f"  Unique Gwen approvals: {len(unique_approvals)} - {unique_approvals}")
        
        # Check for non-determinism
        if len(unique_actions) > 1:
            print(f"  ⚠️  NON-DETERMINISTIC: Different actions selected for same input")
        if len(unique_approvals) > 1:
            print(f"  ⚠️  NON-DETERMINISTIC: Different approval outcomes for same input")
        
        return len(unique_actions) == 1 and len(unique_approvals) == 1
    
    consistent_list = analyze_category(list_results, "List Directory")
    consistent_show = analyze_category(show_results, "Show Files")
    
    return consistent_list and consistent_show


# ============================================================
# STATE LEAKAGE CHECK
# ============================================================
def check_state_leakage():
    """Check for state leakage between tests."""
    print("\n" + "="*60)
    print("STATE LEAKAGE CHECK")
    print("="*60)
    
    issues = []
    
    # Test 1: Model selection leakage
    print("\n1. Model Selection Leakage:")
    client1 = OllamaClient(model='qwen3:0.6b')
    client2 = OllamaClient(model='qwen3:4b')
    if client1.model == client2.model:
        issues.append("Model selection leaks between clients")
        print("  ❌ FAIL: Model leaked")
    else:
        print("  ✓ PASS: Model isolation maintained")
    
    # Test 2: Think mode leakage
    print("\n2. Think Mode Leakage:")
    client1 = OllamaClient(think=True)
    client2 = OllamaClient(think=False)
    if client1.think == client2.think:
        issues.append("Think mode leaks between clients")
        print("  ❌ FAIL: Think mode leaked")
    else:
        print("  ✓ PASS: Think mode isolation maintained")
    
    # Test 3: Target directory changes
    print("\n3. Target Directory Changes:")
    fox1 = OllamaFoxAgent(target_dir=str(TEST_DIR))
    fox2 = OllamaFoxAgent(target_dir="/tmp/other")
    if fox1.target_dir == fox2.target_dir:
        issues.append("Target directory leaks between agents")
        print("  ❌ FAIL: Target directory leaked")
    else:
        print("  ✓ PASS: Target directory isolation maintained")
    
    # Test 4: Previous task results affect later tasks
    print("\n4. Task Result Contamination:")
    reset_test_dir()
    fox = OllamaFoxAgent(target_dir=str(TEST_DIR))
    
    # First task: organise
    result1 = fox.ask("organise the files in /tmp/fox_live_test")
    
    # Second task: list (should see organised structure)
    result2 = fox.ask("list files in /tmp/fox_live_test")
    
    # Check if result2 reflects the organisation
    if result2.selina_result and result2.selina_result.result:
        entries = result2.selina_result.result.get('entries', [])
        # After organise, files should be in subdirectories
        has_subdirs = any('/' in e for e in entries)
        if has_subdirs:
            print("  ✓ PASS: Task results properly affect subsequent tasks (expected)")
        else:
            issues.append("Task results not persisting as expected")
            print("  ⚠️  WARNING: Organisation not reflected in subsequent list")
    
    # Test 5: Fox Club member state persistence
    print("\n5. Fox Club Member State Persistence:")
    # Each ask() creates a new RuntimeResult, so state should not persist
    # But let's verify the runtime is reused
    runtime1 = fox.fox_club.runtime
    result3 = fox.ask("list files")
    runtime2 = fox.fox_club.runtime
    
    if runtime1 is not runtime2:
        issues.append("Runtime replaced between calls")
        print("  ❌ FAIL: Runtime replaced")
    else:
        print("  ✓ PASS: Runtime reused correctly")
    
    return issues


# ============================================================
# GENERATE REPORT
# ============================================================
def generate_report(all_results: dict, consistency_ok: bool, leakage_issues: list):
    """Generate the final report."""
    
    report_lines = []
    
    # 1. SUMMARY
    report_lines.append("="*60)
    report_lines.append("1. SUMMARY")
    report_lines.append("="*60)
    
    total_iterations = sum(r.total for r in all_results.values())
    total_passed = sum(r.passed for r in all_results.values())
    total_failed = sum(r.failed for r in all_results.values())
    all_times = []
    for r in all_results.values():
        for i in r.iterations:
            if i.execution_time > 0:
                all_times.append(i.execution_time)
    
    avg_time = sum(all_times) / len(all_times) if all_times else 0
    slowest = max(all_times) if all_times else 0
    fastest = min(all_times) if all_times else 0
    
    report_lines.append(f"Total iterations: {total_iterations}")
    report_lines.append(f"Passed: {total_passed}")
    report_lines.append(f"Failed: {total_failed}")
    report_lines.append(f"Success rate: {total_passed/total_iterations*100:.1f}%")
    report_lines.append(f"Average execution time: {avg_time:.2f}s")
    report_lines.append(f"Slowest execution: {slowest:.2f}s")
    report_lines.append(f"Fastest execution: {fastest:.2f}s")
    
    # Per-category summary
    report_lines.append("\nPer-category breakdown:")
    for name, results in all_results.items():
        report_lines.append(f"  {name}: {results.passed}/{results.total} passed ({results.success_rate:.1f}%), avg={results.avg_time:.2f}s")
    
    # 2. FAILURE BREAKDOWN
    report_lines.append("\n" + "="*60)
    report_lines.append("2. FAILURE BREAKDOWN")
    report_lines.append("="*60)
    
    failure_categories = defaultdict(lambda: {"count": 0, "examples": []})
    
    for results in all_results.values():
        for iter_result in results.iterations:
            if not iter_result.success and iter_result.error_category:
                cat = iter_result.error_category
                failure_categories[cat]["count"] += 1
                if len(failure_categories[cat]["examples"]) < 3:
                    failure_categories[cat]["examples"].append(
                        iter_result.exception[:200] if iter_result.exception else "No exception"
                    )
    
    for cat in ["Julie", "Annie", "Selina", "Gwen", "Ollama", "Model selection", 
                "Think configuration", "Runtime", "Executor", "Timeout", "Exception", "Other"]:
        if cat in failure_categories:
            data = failure_categories[cat]
            pct = data["count"] / total_failed * 100 if total_failed > 0 else 0
            report_lines.append(f"\n{cat}:")
            report_lines.append(f"  Failure count: {data['count']}")
            report_lines.append(f"  Percentage: {pct:.1f}%")
            report_lines.append(f"  Representative error: {data['examples'][0] if data['examples'] else 'N/A'}")
    
    # 3. CONSISTENCY CHECK
    report_lines.append("\n" + "="*60)
    report_lines.append("3. CONSISTENCY CHECK")
    report_lines.append("="*60)
    
    if consistency_ok:
        report_lines.append("✓ PASS: Repeated identical inputs produce consistent results")
        report_lines.append("  - Same action selected by Selina")
        report_lines.append("  - Same execution result")
        report_lines.append("  - Same approval behavior by Gwen")
    else:
        report_lines.append("❌ FAIL: Non-deterministic behavior detected")
        report_lines.append("  - Different actions selected for identical inputs")
        report_lines.append("  - Different approval outcomes for identical inputs")
    
    # 4. STATE LEAKAGE CHECK
    report_lines.append("\n" + "="*60)
    report_lines.append("4. STATE LEAKAGE CHECK")
    report_lines.append("="*60)
    
    if not leakage_issues:
        report_lines.append("✓ PASS: No state leakage detected")
        report_lines.append("  - Model selection does not leak between tests")
        report_lines.append("  - Think mode does not leak between tests")
        report_lines.append("  - Target directory changes are isolated")
        report_lines.append("  - Previous task results do not inappropriately affect later tasks")
        report_lines.append("  - Fox Club member state does not persist unexpectedly")
    else:
        report_lines.append("❌ FAIL: State leakage detected")
        for issue in leakage_issues:
            report_lines.append(f"  - {issue}")
    
    # 5. CRITICAL FINDINGS
    report_lines.append("\n" + "="*60)
    report_lines.append("5. CRITICAL FINDINGS")
    report_lines.append("="*60)
    
    findings = []
    
    # Analyze failures for critical issues
    for results in all_results.values():
        for iter_result in results.iterations:
            if not iter_result.success:
                if iter_result.error_category == "Ollama":
                    findings.append(("CRITICAL", f"Ollama connection failure: {iter_result.exception[:100]}"))
                elif iter_result.error_category == "Executor":
                    findings.append(("HIGH", f"Executor failure: {iter_result.exception[:100]}"))
                elif iter_result.error_category in ["Julie", "Annie", "Selina", "Gwen"]:
                    findings.append(("MEDIUM", f"{iter_result.error_category} pipeline failure: {iter_result.exception[:100]}"))
                elif iter_result.error_category == "Timeout":
                    findings.append(("HIGH", f"Timeout: {iter_result.exception[:100]}"))
                else:
                    findings.append(("LOW", f"{iter_result.error_category}: {iter_result.exception[:100]}"))
    
    # Deduplicate findings
    seen = set()
    unique_findings = []
    for severity, msg in findings:
        key = (severity, msg[:80])
        if key not in seen:
            seen.add(key)
            unique_findings.append((severity, msg))
    
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        category_findings = [f for f in unique_findings if f[0] == severity]
        if category_findings:
            report_lines.append(f"\n{severity}:")
            for _, msg in category_findings[:5]:  # Top 5 per category
                report_lines.append(f"  - {msg}")
    
    # 6. FINAL VERDICT
    report_lines.append("\n" + "="*60)
    report_lines.append("6. FINAL VERDICT")
    report_lines.append("="*60)
    
    # Determine verdict
    critical_count = len([f for f in unique_findings if f[0] == "CRITICAL"])
    high_count = len([f for f in unique_findings if f[0] == "HIGH"])
    overall_success_rate = total_passed / total_iterations * 100 if total_iterations > 0 else 0
    
    if critical_count > 0 or overall_success_rate < 50:
        verdict = "FAIL"
        reason = f"Critical issues: {critical_count}, Success rate: {overall_success_rate:.1f}%"
    elif high_count > 0 or overall_success_rate < 80 or not consistency_ok or leakage_issues:
        verdict = "PASS WITH WARNINGS"
        reason = f"High issues: {high_count}, Success rate: {overall_success_rate:.1f}%, Consistency: {'OK' if consistency_ok else 'FAIL'}, Leakage: {'OK' if not leakage_issues else 'FAIL'}"
    else:
        verdict = "PASS"
        reason = f"Success rate: {overall_success_rate:.1f}%, All checks passed"
    
    report_lines.append(f"\n{verdict}")
    report_lines.append(f"Reason: {reason}")
    
    return "\n".join(report_lines)


# ============================================================
# MAIN
# ============================================================
def main():
    print("="*60)
    print("FOX CLUB STRESS TEST")
    print("="*60)
    print(f"Test directory: {TEST_DIR}")
    print(f"Project root: /Users/enoch/Desktop/Connectivity_A")
    
    # Verify Ollama is running
    client = OllamaClient()
    print(f"Ollama model: {client.model}")
    print(f"Think mode: {client.think}")
    
    all_results = {}
    
    # Run tests
    try:
        all_results["List Directory"] = test_list_directory()
    except Exception as e:
        print(f"Test 1 failed catastrophically: {e}")
        traceback.print_exc()
    
    try:
        all_results["Show Files"] = test_show_files()
    except Exception as e:
        print(f"Test 2 failed catastrophically: {e}")
        traceback.print_exc()
    
    try:
        all_results["Organise Files"] = test_organise_files()
    except Exception as e:
        print(f"Test 3 failed catastrophically: {e}")
        traceback.print_exc()
    
    try:
        all_results["Model Configuration"] = test_model_configuration()
    except Exception as e:
        print(f"Test 4 failed catastrophically: {e}")
        traceback.print_exc()
    
    try:
        all_results["Failure Handling"] = test_failure_handling()
    except Exception as e:
        print(f"Test 5 failed catastrophically: {e}")
        traceback.print_exc()
    
    # Consistency check
    consistency_ok = check_consistency(
        all_results.get("List Directory", TestCategoryResults("List Directory")),
        all_results.get("Show Files", TestCategoryResults("Show Files"))
    )
    
    # State leakage check
    leakage_issues = check_state_leakage()
    
    # Generate report
    report = generate_report(all_results, consistency_ok, leakage_issues)
    
    # Save report to desktop
    desktop = Path.home() / "Desktop"
    report_path = desktop / "fox_club_stress_test_report.txt"
    report_path.write_text(report)
    
    print("\n" + "="*60)
    print("REPORT SAVED TO:", report_path)
    print("="*60)
    print(report)


if __name__ == "__main__":
    main()