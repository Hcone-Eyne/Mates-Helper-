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


console = Console()


class _UnavailableExecutor:
    """Executor used until the runtime is wired to real tools."""

    # this function makes the missing tool wiring explicit instead of crashing
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

    # Adding refinement limits
    MAX_REFINEMENTS = 3

    def __init__(
        self,
        julie: Julie,
        annie: Annie,
        selina: Selina,
        gwen: Gwen,
    ):
        # this function stores each Club member for pipeline coordination
        self.julie = julie
        self.annie = annie
        self.selina = selina
        self.gwen = gwen

    def handle(self, user_input: str) -> RuntimeResult:
        """
        Send one user request through the Fox Club pipeline.
        """

        # this validates the incoming request before starting the pipeline
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
        # STEP 4: GWEN
        # ---------------------------------------------------------
        # changed -> Gwen review is handled by controlled refinement loop below!


        # ---------------------------------------------------------
        # STEP 5: FINAL RESULT
        # ---------------------------------------------------------
        # For the first Runtime version, we return Selina's result
        # together with Gwen's review.
        
        # refinment count if exceeed, refinement will be stoped by conditions.....
        refinement_count = 0

        # loop for refiment process
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
        # Return the latest attempt, together with Gwen's final review.

        # The refinement loop will be added next.
        return RuntimeResult(
            user_request=user_input,
            julie_result=julie_result,
            annie_result=annie_result,
            selina_result=selina_result,
            gwen_result=gwen_result,
            final_result=selina_result
        )


def build_runtime(target_dir: str | Path | None = None) -> Runtime:
    """Create a Runtime wired to a local Ollama server.

    When *target_dir* is provided, Selina receives a real
    FileActionExecutor scoped to that directory.  Otherwise the
    legacy ``_UnavailableExecutor`` is used.
    """
    try:
        client = OllamaClient(model="qwen2.5:3b-instruct")
    except RuntimeError as exc:
        raise RuntimeError(
            f"[Runtime]: Cannot start — Ollama is unavailable: {exc}"
        ) from exc

    julie = Julie(OllamaReasoningBackend(client))
    annie = Annie(OllamaAnnieBackend(client))

    if target_dir is not None:
        executor = FileActionExecutor(Path(target_dir))
    else:
        executor = _UnavailableExecutor()

    selina = Selina(executor)
    gwen = Gwen(OllamaCriticBackend(client))

    return Runtime(julie=julie, annie=annie, selina=selina, gwen=gwen)


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


def run_fox_club():
    """Interactive CLI loop for the Fox Club pipeline."""
    os.system("clear")

    console.print(
        Panel.fit(
            "[bold green]Fox Club Pipeline[/bold green]\n"
            "Flow: Julie -> Annie -> Selina -> Gwen",
            title="[Fox]: Setup"
        )
    )

    # Prompt for the target folder to organise.
    target_input = input("\n[You]: Enter the folder path to organise (or press Enter to skip): ").strip()

    target_dir = None
    if target_input:
        try:
            target_dir = validate_target_dir(target_input)
            console.print(f"[green][Fox]: Target folder set to {target_dir}[/green]")
        except ValueError as exc:
            console.print(f"[red][Fox]: {exc}[/red]")
            console.print("[yellow][Fox]: Continuing without executor.[/yellow]")

    try:
        runtime = build_runtime(target_dir=target_dir)
    except RuntimeError as exc:
        console.print(f"[red][Fox]: {exc}[/red]")
        input("\nPress Enter to continue...")
        return

    mode_label = f"Target: [cyan]{target_dir}[/cyan]" if target_dir else "Mode: [yellow]no executor[/yellow]"
    console.print(
        Panel.fit(
            f"{mode_label}\n"
            "Type [bold]exit[/bold] to return.",
            title="[Fox]: Club Members"
        )
    )

    while True:
        try:
            user_input = input("\n[You]: ").strip()

            if not user_input:
                continue

            if user_input.lower() in {"exit", "quit", "0"}:
                break

            # Run the full pipeline.
            result = runtime.handle(user_input)

            # Display results step by step.
            console.print(f"\n[bold cyan]--- Julie ---[/bold cyan]")
            console.print(f"Task: {result.julie_result.expanded_task}")
            console.print(f"Plan: {', '.join(result.julie_result.plan)}")
            if result.julie_result.uncertainty:
                console.print(f"Uncertainty: {', '.join(result.julie_result.uncertainty)}")

            console.print(f"\n[bold cyan]--- Annie ---[/bold cyan]")
            console.print(f"Interpretation: {result.annie_result.interpretation}")
            console.print(f"Requirements: {', '.join(result.annie_result.requirements)}")
            console.print(f"Constraints: {', '.join(result.annie_result.constraints)}")
            console.print(f"Handoff: {result.annie_result.technical_handoff}")
            if result.annie_result.clarification_needed:
                console.print(f"Clarification: {', '.join(result.annie_result.clarification_needed)}")

            console.print(f"\n[bold cyan]--- Selina ---[/bold cyan]")
            console.print(f"Action: {result.selina_result.action}")
            console.print(f"Success: {result.selina_result.success}")
            console.print(f"Result: {result.selina_result.result}")
            if result.selina_result.error:
                console.print(f"Error: {result.selina_result.error}")

            console.print(f"\n[bold cyan]--- Gwen ---[/bold cyan]")
            gwen = result.gwen_result
            status = "[green]APPROVED[/green]" if gwen.approved else "[red]REJECTED[/red]"
            console.print(f"Status: {status}")
            console.print(f"Critique: {gwen.critique}")
            if gwen.issues:
                console.print(f"Issues: {', '.join(gwen.issues)}")
            if gwen.safety_concerns:
                console.print(f"Safety: {', '.join(gwen.safety_concerns)}")
            if gwen.recommendations:
                console.print(f"Recommendations: {', '.join(gwen.recommendations)}")

        except KeyboardInterrupt:
            break
        except Exception as exc:
            console.print(f"\n[red][Fox]: Error: {exc}[/red]")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    run_fox_club()
