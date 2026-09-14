# testing the runtime!
"""Tests for Fox Club Runtime refinement flow."""

import sys
import os

# Ensure repo root is on sys.path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.fox.runtime.runtime import Runtime
from agent.julie.julie import JulieResult
from agent.annie.annie import AnnieResult
from agent.selina.selina import SelinaResult
from agent.gwen.gwen import GwenResult


class FakeJulie:
    def __init__(self):
        self.calls = 0

    def reason(self, user_input):
        self.calls += 1

        return JulieResult(
            user_request=user_input,
            context=None,
            expanded_task="Test task",
            plan=["test_action"],
            uncertainty=[],
            raw_response="test",
        )


class FakeAnnie:
    def __init__(self):
        self.structure_calls = 0
        self.refine_calls = 0

    def structure(self, julie_result):
        self.structure_calls += 1

        return AnnieResult(
            user_request=julie_result.user_request,
            interpretation="Test interpretation",
            requirements=["test requirement"],
            constraints=[],
            technical_handoff="test handoff",
            clarification_needed=[],
            raw_response="test",
        )

    def refine(self, previous_result, selina_feedback):
        self.refine_calls += 1

        return AnnieResult(
            user_request=previous_result.user_request,
            interpretation="Refined interpretation",
            requirements=["refined requirement"],
            constraints=[],
            technical_handoff="refined handoff",
            clarification_needed=[],
            raw_response="refined",
        )


class FakeSelina:
    def __init__(self):
        self.calls = 0

    def execute_from_annie(self, annie_result):
        self.calls += 1

        return SelinaResult(
            success=True,
            expanded_task="Test task",
            interpretation=annie_result.interpretation,
            action="test_action",
            result="success",
            error=None,
        )


class FakeGwen:
    def __init__(self, reviews):
        self.reviews = iter(reviews)
        self.calls = 0

    def review_structured(
        self,
        user_request,
        julie_result,
        selina_result,
        annie_result,
    ):
        self.calls += 1
        return next(self.reviews)

def test_runtime_approves_without_refinement():
    """Runtime should stop immediately when Gwen approves."""

    julie = FakeJulie()
    annie = FakeAnnie()
    selina = FakeSelina()

    gwen = FakeGwen([
        GwenResult(
            approved=True,
            reasoning="Everything looks correct.",
            critique="",
            issues=[],
            safety_concerns=[],
            recommendations=[],
        )
    ])

    runtime = Runtime(
        julie=julie,
        annie=annie,
        selina=selina,
        gwen=gwen,
    )

    result = runtime.handle("Test request")

    # Julie runs once.
    assert julie.calls == 1

    # Annie.structure() runs once.
    assert annie.structure_calls == 1

    # No refinement should happen.
    assert annie.refine_calls == 0

    # Selina executes the initial attempt once.
    assert selina.calls == 1

    # Gwen reviews the initial attempt once.
    assert gwen.calls == 1

    # Final result should be the Selina result.
    assert result.selina_result.success is True

def test_runtime_refines_once_then_approves():
    """Runtime should refine Annie once when Gwen rejects, then approve."""

    julie = FakeJulie()
    annie = FakeAnnie()
    selina = FakeSelina()

    gwen = FakeGwen([
        # First review rejects the initial execution.
        GwenResult(
            approved=False,
            reasoning="The interpretation needs correction.",
            critique="The technical handoff needs refinement.",
            issues=["Incorrect interpretation"],
            safety_concerns=[],
            recommendations=["Refine the handoff"],
        ),

        # Second review approves the refined execution.
        GwenResult(
            approved=True,
            reasoning="The refined result is correct.",
            critique="",
            issues=[],
            safety_concerns=[],
            recommendations=[],
        ),
    ])

    runtime = Runtime(
        julie=julie,
        annie=annie,
        selina=selina,
        gwen=gwen,
    )

    result = runtime.handle("Test request")

    # Julie should NOT run again during refinement.
    assert julie.calls == 1

    # Annie.structure() should run only once.
    assert annie.structure_calls == 1

    # Annie.refine() should run once.
    assert annie.refine_calls == 1

    # Selina should execute once initially + once after refinement.
    assert selina.calls == 2

    # Gwen should review both attempts.
    assert gwen.calls == 2

    # The final Annie result should be the refined one.
    assert result.annie_result.interpretation == "Refined interpretation"

    # The final Selina result should come from the refined Annie result.
    assert result.selina_result.interpretation == "Refined interpretation"

    # Gwen approved the final attempt.
    assert result.gwen_result.approved is True

def test_runtime_stops_on_safety_concern():
    """Runtime should stop immediately when Gwen reports a safety concern."""

    julie = FakeJulie()
    annie = FakeAnnie()
    selina = FakeSelina()

    gwen = FakeGwen([
        GwenResult(
            approved=False,
            reasoning="The requested action is unsafe.",
            critique="Do not execute this action again.",
            issues=["Unsafe action"],
            safety_concerns=["Potentially destructive operation"],
            recommendations=["Stop execution"],
        )
    ])

    runtime = Runtime(
        julie=julie,
        annie=annie,
        selina=selina,
        gwen=gwen,
    )

    result = runtime.handle("Test request")

    # Julie should run only once.
    assert julie.calls == 1

    # Annie.structure() should run only once.
    assert annie.structure_calls == 1

    # Safety concern must prevent refinement.
    assert annie.refine_calls == 0

    # Selina should execute only the initial attempt.
    assert selina.calls == 1

    # Gwen should review only once.
    assert gwen.calls == 1

    # Final Gwen result must preserve the safety concern.
    assert result.gwen_result.approved is False
    assert result.gwen_result.safety_concerns == [
        "Potentially destructive operation"
    ]
def test_runtime_stops_after_max_refinements():
    """Runtime should stop after reaching the maximum refinement limit."""

    julie = FakeJulie()
    annie = FakeAnnie()
    selina = FakeSelina()

    gwen = FakeGwen([
        GwenResult(
            approved=False,
            reasoning="Still incorrect.",
            critique="Needs another refinement.",
            issues=["Issue remains"],
            safety_concerns=[],
            recommendations=[],
        ),
        GwenResult(
            approved=False,
            reasoning="Still incorrect.",
            critique="Needs another refinement.",
            issues=["Issue remains"],
            safety_concerns=[],
            recommendations=[],
        ),
        GwenResult(
            approved=False,
            reasoning="Still incorrect.",
            critique="Needs another refinement.",
            issues=["Issue remains"],
            safety_concerns=[],
            recommendations=[],
        ),
        GwenResult(
            approved=False,
            reasoning="Still incorrect.",
            critique="Should not reach another refinement.",
            issues=["Issue remains"],
            safety_concerns=[],
            recommendations=[],
        ),
    ])

    runtime = Runtime(
        julie=julie,
        annie=annie,
        selina=selina,
        gwen=gwen,
    )

    result = runtime.handle("Test request")

    assert julie.calls == 1
    assert annie.structure_calls == 1
    assert annie.refine_calls == 3
    assert selina.calls == 4
    assert gwen.calls == 4
    assert result.gwen_result.approved is False


# ------------------------------------------------------------------
# build_runtime() wiring tests
# ------------------------------------------------------------------

import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent.fox.runtime.runtime import build_runtime, _UnavailableExecutor
from agent.fox.runtime.executor import FileActionExecutor


def test_build_runtime_with_target_dir_wires_file_action_executor():
    """build_runtime(target_dir) must inject FileActionExecutor into Selina."""
    tmp = tempfile.mkdtemp(prefix="fox_build_")
    try:
        with patch("agent.fox.runtime.runtime.OllamaClient") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            runtime = build_runtime(target_dir=tmp)

        # Selina's executor must be a FileActionExecutor.
        assert isinstance(runtime.selina.executor, FileActionExecutor)
        # The executor's target must resolve to the supplied directory.
        assert runtime.selina.executor._target == Path(tmp).resolve()
    finally:
        shutil.rmtree(tmp)


def test_build_runtime_without_target_dir_wires_unavailable_executor():
    """build_runtime() with no target must use _UnavailableExecutor."""
    with patch("agent.fox.runtime.runtime.OllamaClient") as mock_client_cls:
        mock_client_cls.return_value = MagicMock()
        runtime = build_runtime()

    assert isinstance(runtime.selina.executor, _UnavailableExecutor)


def test_build_runtime_none_does_not_create_filesystem_target():
    """build_runtime(None) must not create any directory as a side effect."""
    with patch("agent.fox.runtime.runtime.OllamaClient") as mock_client_cls:
        mock_client_cls.return_value = MagicMock()
        # Pass None explicitly — same as calling with no arguments.
        runtime = build_runtime(target_dir=None)

    # Executor must be the unavailable placeholder.
    assert isinstance(runtime.selina.executor, _UnavailableExecutor)

    # The executor must not have a _target attribute (it's not filesystem-aware).
    assert not hasattr(runtime.selina.executor, "_target")


# ------------------------------------------------------------------
# validate_target_dir() tests
# ------------------------------------------------------------------

from agent.fox.runtime.runtime import validate_target_dir


def test_validate_target_dir_empty_string_returns_none():
    """Empty input should return None (no executor)."""
    assert validate_target_dir("") is None


def test_validate_target_dir_whitespace_returns_none():
    """Whitespace-only input should return None (no executor)."""
    assert validate_target_dir("   ") is None


def test_validate_target_dir_valid_directory():
    """An existing directory should resolve to a Path."""
    tmp = tempfile.mkdtemp(prefix="fox_validate_")
    try:
        result = validate_target_dir(tmp)
        assert result == Path(tmp).resolve()
    finally:
        shutil.rmtree(tmp)


def test_validate_target_dir_nonexistent_path_rejected():
    """A nonexistent path should raise ValueError."""
    try:
        validate_target_dir("/tmp/this_does_not_exist_12345")
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "does not exist" in str(exc)


def test_validate_target_dir_file_rejected():
    """A path pointing to a file (not directory) should raise ValueError."""
    tmp = tempfile.mkdtemp(prefix="fox_file_")
    try:
        filepath = Path(tmp) / "not_a_dir.txt"
        filepath.write_text("hello")
        try:
            validate_target_dir(str(filepath))
            assert False, "Should have raised ValueError"
        except ValueError as exc:
            assert "not a directory" in str(exc)
    finally:
        shutil.rmtree(tmp)


def test_validate_target_dir_tilde_expanded():
    """Tilde (~) should be expanded to the home directory."""
    result = validate_target_dir("~")
    assert result == Path("~").expanduser().resolve()
    assert result.is_dir()