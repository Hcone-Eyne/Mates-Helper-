# Runtime is the main coordinator for Fox Club.
# It connects Julie -> Annie -> Selina -> Gwen.

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel

from agent.julie.julie import Julie, JulieResult, OllamaReasoningBackend
from agent.annie.annie import Annie, AnnieResult, OllamaAnnieBackend
from agent.selina.selina import Selina, SelinaResult
from agent.gwen.gwen import Gwen, OllamaCriticBackend
from agent.ollama.client import OllamaClient
from agent.fox.runtime.executor import FileActionExecutor
from agent.fox.security import FoxSecurityBoundary
from agent.fox.Fox_Space import ensure_fox_space


console = Console()


class _UnavailableExecutor:
    """Placeholder executor used when no target directory is configured."""

    def execute(self, action: str, arguments: dict[str, Any]) -> Any:
        raise RuntimeError(
            f"[Runtime]: No action executor is configured for '{action}'."
        )


@dataclass(frozen=True)
class RuntimeResult:
    # Original request from the user.
    user_request: str

    # Results produced by each Club member.
    julie_result: JulieResult
    annie_result: AnnieResult
    selina_result: SelinaResult

    # Gwen's final review.
    gwen_result: Any

    # Final response returned by Runtime.
    final_result: Any


class Runtime:
    """
    Main Fox Club orchestrator.

    Flow:

        User
          ↓
        Julie
          ↓
        Annie
          ↓
        Selina
          ↓
        Gwen
          ↓
        Final result
    """

    MAX_REFINEMENTS = 3

    def __init__(
        self,
        julie: Julie,
        annie: Annie,
        selina: Selina,
        gwen: Gwen,
    ):
        self.julie = julie
        self.annie = annie
        self.selina = selina
        self.gwen = gwen

    def handle(self, user_input: str) -> RuntimeResult:
        """Send one user request through the Fox Club pipeline."""

        if not isinstance(user_input, str):
            raise TypeError(
                "[Runtime]: user_input must be a string."
            )

        if not user_input.strip():
            raise ValueError(
                "[Runtime]: user_input cannot be empty."
            )

        # ---------------------------------------------------------
        # STEP 1: JULIE
        # ---------------------------------------------------------
        # Julie understands the user's request and expands it
        # into semantic reasoning.
        julie_result = self.julie.reason(user_input)

        # this checks that Julie returned the expected result type
        if not isinstance(julie_result, JulieResult):
            raise TypeError(
                "[Runtime]: Julie returned an invalid result."
            )

        # ---------------------------------------------------------
        # STEP 2: ANNIE
        # ---------------------------------------------------------
        # Annie receives Julie's reasoning and converts it into
        # a structured engineering handoff for Selina.
        annie_result = self.annie.structure(julie_result)

        # this checks that Annie produced a valid handoff
        if not isinstance(annie_result, AnnieResult):
            raise TypeError(
                "[Runtime]: Annie returned an invalid result."
            )

        # ---------------------------------------------------------
        # STEP 3: SELINA
        # ---------------------------------------------------------
        # Selina performs the actual technical execution.
        selina_result = self.selina.execute_from_annie(
            annie_result
        )

        # this checks that Selina returned the expected result type
        if not isinstance(selina_result, SelinaResult):
            raise TypeError(
                "[Runtime]: Selina returned an invalid result."
            )

        # ---------------------------------------------------------
        # STEP 4: GWEN (handled by refinement loop below)
        # ---------------------------------------------------------


        # ---------------------------------------------------------
        # STEP 5: REFINEMENT LOOP
        # ---------------------------------------------------------
        # Gwen reviews the current attempt.  If she rejects it and
        # there are no safety concerns, Annie refines the handoff
        # and Selina re-executes until Gwen approves or the limit
        # is reached.

        refinement_count = 0
        while True:
            # this asks Gwen to review the current pipeline attempt
            gwen_result = self.gwen.review_structured(
                user_request=user_input,
                julie_result=julie_result,
                selina_result=selina_result,
                annie_result=annie_result,
            )

            # this stops immediately when Gwen approves the result
            if gwen_result.approved:
                break

            # this stops on safety concerns instead of retrying automatically
            if gwen_result.safety_concerns:
                break

            # this stops when the refinement limit has been reached
            if refinement_count >= self.MAX_REFINEMENTS:
                break

            # this sends Gwen's feedback to Annie for a corrected handoff
            annie_result = self.annie.refine(
                previous_result = annie_result,
                selina_feedback = gwen_result.critique
            )

            # this executes the refined handoff through Selina
            selina_result = self.selina.execute_from_annie(annie_result)

            # this checks that the refined execution returned a valid result
            if not isinstance(selina_result, SelinaResult):
                raise TypeError("[Runtime]: Selina returned an invalid result.....")

            refinement_count += 1

        # ---------------------------------------------------------
        # STEP 6: FINAL RESULT
        # ---------------------------------------------------------
        # Return the latest attempt together with Gwen's final review.
        return RuntimeResult(
            user_request=user_input,
            julie_result=julie_result,
            annie_result=annie_result,
            selina_result=selina_result,
            gwen_result=gwen_result,
            final_result=selina_result
        )


def build_runtime(
    target_dir: str | Path | None = None,
    model: str | None = None,
    think: bool = False
) -> Runtime:
    """Create a Runtime wired to a local Ollama server."""
    try:
        client = OllamaClient(
            model=model,
            think=think
        )
    except RuntimeError as exc:
        raise RuntimeError(
            f"[Runtime]: Cannot start — Ollama is unavailable: {exc}"
        ) from exc

    julie = Julie(OllamaReasoningBackend(client))
    annie = Annie(OllamaAnnieBackend(client))

    fox_space = ensure_fox_space()
    if target_dir is not None:
        executor_root = Path(target_dir)
    else:
        executor_root = fox_space

    boundary = FoxSecurityBoundary(executor_root)
    executor = FileActionExecutor(boundary)

    selina = Selina(executor)
    gwen = Gwen(OllamaCriticBackend(client))

    return Runtime(
        julie=julie,
        annie=annie,
        selina=selina,
        gwen=gwen
    )


def validate_target_dir(raw_input: str) -> Path | None:
    """Validate and resolve a user-supplied target directory path.

    Returns the resolved Path if valid, or None if the input is empty.
    Raises ValueError for invalid (non-empty) paths.
    """
    raw_input = raw_input.strip()

    if not raw_input:
        return None

    path = Path(raw_input).expanduser().resolve()

    if not path.exists():
        raise ValueError(f"Path does not exist: {path}")

    if not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    return path