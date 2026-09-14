# Runtime is the main coordinator for Fox Club.
# It connects Julie -> Annie -> Selina -> Gwen.

import os
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.panel import Panel

from agent.julie.julie import Julie, JulieResult, OllamaReasoningBackend
from agent.annie.annie import Annie, AnnieResult, OllamaAnnieBackend
from agent.selina.selina import Selina, SelinaResult
from agent.gwen.gwen import Gwen, GwenResult, OllamaCriticBackend
from agent.ollama.client import OllamaClient


console = Console()


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

    def __init__(
        self,
        julie: Julie,
        annie: Annie,
        selina: Selina,
        gwen: Gwen,
    ):
        # Store each Club member so Runtime can coordinate them.
        self.julie = julie
        self.annie = annie
        self.selina = selina
        self.gwen = gwen

    def handle(self, user_input: str) -> RuntimeResult:
        """
        Send one user request through the Fox Club pipeline.
        """

        # Validate the incoming request before starting the pipeline.
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

        # Make sure Julie actually returned the expected result.
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

        # Make sure Annie produced a valid handoff.
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

        # Make sure Selina returned the expected result.
        if not isinstance(selina_result, SelinaResult):
            raise TypeError(
                "[Runtime]: Selina returned an invalid result."
            )

        # ---------------------------------------------------------
        # STEP 4: GWEN
        # ---------------------------------------------------------
        # Gwen checks the result produced by Selina against
        # the original reasoning, Annie's handoff, and Selina's execution.
        gwen_result = self.gwen.review_structured(
            user_request=user_input,
            julie_result=julie_result,
            selina_result=selina_result,
            annie_result=annie_result,
        )

        # ---------------------------------------------------------
        # STEP 5: FINAL RESULT
        # ---------------------------------------------------------
        # For the first Runtime version, we return Selina's result
        # together with Gwen's review.
        #
        # The refinement loop will be added next.
        return RuntimeResult(
            user_request=user_input,
            julie_result=julie_result,
            annie_result=annie_result,
            selina_result=selina_result,
            gwen_result=gwen_result,
            final_result=selina_result,
        )


def build_runtime() -> Runtime:
    """Create a Runtime wired to a local Ollama server."""
    try:
        client = OllamaClient(model="qwen2.5:3b-instruct")
    except RuntimeError as exc:
        raise RuntimeError(
            f"[Runtime]: Cannot start — Ollama is unavailable: {exc}"
        ) from exc

    julie = Julie(OllamaReasoningBackend(client))
    annie = Annie(OllamaAnnieBackend(client))
    selina = Selina(None)  # executor wired later when tools are ready
    gwen = Gwen(OllamaCriticBackend(client))

    return Runtime(julie=julie, annie=annie, selina=selina, gwen=gwen)


def run_fox_club():
    """Interactive CLI loop for the Fox Club pipeline."""
    os.system("clear")

    try:
        runtime = build_runtime()
    except RuntimeError as exc:
        console.print(f"[red][Fox]: {exc}[/red]")
        input("\nPress Enter to continue...")
        return

    console.print(
        Panel.fit(
            "[bold green]Fox Club Pipeline[/bold green]\n"
            f"Model: [cyan]qwen2.5:3b-instruct[/cyan]\n"
            "Flow: Julie -> Annie -> Selina -> Gwen\n"
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
