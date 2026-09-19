# Selina - She is the one proceed with the tasks..
# aka have the most powerfull part in this.....

# importing the nessary modules
import re
from dataclasses import dataclass
from typing import Any, Protocol

from agent.julie.julie import JulieResult
from agent.annie.annie import AnnieResult


# Explicit mapping of supported actions to their trigger keywords.
# Each keyword is matched as a whole word inside a normalized requirement.
# To add a new action, add an entry here AND implement it in the executor.
SUPPORTED_ACTIONS = {
    "organise_folder": [
        "organise",
        "organize",
        "sort",
        "categorize",
        "category",
    ],
    "list_directory": [
        "list",
        "show",
        "display",
        "contents",
        "directory",
    ],
    "find_files": [
        "search",
        "find",
        "locate",
        "look",
    ],
}

def _resolve_action(requirements: list[str]) -> str:
    """Scan all requirements and return the first matching supported action.

    Matching uses whole-word regex against each keyword.  Returns the
    first matched action name, or "" if no action could be resolved.
    """
    for req in requirements:
        normalized = req.strip().lower()
        for action_name, keywords in SUPPORTED_ACTIONS.items():
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw)}\b", normalized):
                    return action_name
    return ""

# this class is used to perform the task selina needs
class ActionExecutor(Protocol):
    # Every executor must provide this method so Selina can run an action.
    def execute(self, action: str, arguments: dict[str, Any]) -> Any:
        ...

@dataclass(frozen=True)
class SelinaResult:
    # Store both the decision Selina made and what happened when it ran it.
    success: bool
    expanded_task: str
    interpretation: str
    action: str
    result: Any = None
    error: str | None = None

# this class is for Selina the core!
class Selina():

    # adding the initializer
    def __init__(self, executor: ActionExecutor):
        # Keep the executor that will perform the selected action.
        self.executor = executor

    def execute(self, julie_result: JulieResult) -> SelinaResult:

        # validate julie_result
        if not isinstance(julie_result, JulieResult):
            raise TypeError(
                "[Selina]: Input must be a JulieResult."
            )

        # Read the full task description produced by Julie.
        expanded_task = julie_result.expanded_task

        # Stop before executing anything if Julie returned no usable task.
        if not expanded_task or not expanded_task.strip():
            return SelinaResult(
                success=False,
                expanded_task="",
                interpretation="",
                action="",
                error="Expanded task is empty."
            )

        # Turn Julie's task and steps into a readable explanation.
        interpretation = self._interpret(julie_result)

        # Convert the first planned step into the action name to execute.
        action = self._determine_action(julie_result)

        # Stop if the plan did not contain a step that can become an action.
        if not action:
            return SelinaResult(
                success=False,
                expanded_task=expanded_task,
                interpretation=interpretation,
                action="",
                error="Could not determine an action from the plan."
            )

        # Collect the task data that the executor may need.
        arguments = self._build_arguments(julie_result)

        try:
            # Ask the executor to carry out the action selected above.
            result = self.executor.execute(
                action=action,
                arguments=arguments
            )

            # Return the successful action result to the caller.
            return SelinaResult(
                success=True,
                expanded_task=expanded_task,
                interpretation=interpretation,
                action=action,
                result=result
            )

        except Exception as exc:
            # Report executor failures as a failed result instead of hiding them.
            return SelinaResult(
                success=False,
                expanded_task=expanded_task,
                interpretation=interpretation,
                action=action,
                error=str(exc)
            )

    def execute_from_annie(
        self,
        annie_result: AnnieResult,
        action: str | None = None,
    ) -> SelinaResult:
        # Validate the AnnieResult before processing.
        if not isinstance(annie_result, AnnieResult):
            raise TypeError(
                "[Selina]: Input must be an AnnieResult."
            )

        # Use the technical handoff as the task description.
        expanded_task = annie_result.technical_handoff

        if not expanded_task or not expanded_task.strip():
            return SelinaResult(
                success=False,
                expanded_task="",
                interpretation="",
                action="",
                error="Annie's technical_handoff is empty."
            )

        # Use Annie's interpretation directly — no need to build from plan.
        interpretation = annie_result.interpretation

        # Determine the action: use provided action or derive from first requirement.
        if action is None:
            action = self._action_from_requirements(annie_result)

        if not action:
            return SelinaResult(
                success=False,
                expanded_task=expanded_task,
                interpretation=interpretation,
                action="",
                error="Could not determine an action from Annie's requirements."
            )

        # Build arguments from Annie's structured fields.
        arguments = self._build_arguments_from_annie(annie_result)

        try:
            result = self.executor.execute(
                action=action,
                arguments=arguments,
            )

            return SelinaResult(
                success=True,
                expanded_task=expanded_task,
                interpretation=interpretation,
                action=action,
                result=result,
            )

        except Exception as exc:
            return SelinaResult(
                success=False,
                expanded_task=expanded_task,
                interpretation=interpretation,
                action=action,
                error=str(exc),
            )

    @staticmethod
    def _interpret(julie_result: JulieResult) -> str:
        """Interpret what needs to happen based on Julie's reasoning."""
        # Pull out the task and ordered plan steps for the explanation.
        task = julie_result.expanded_task
        steps = julie_result.plan

        # Explain that no plan was supplied when the steps list is empty.
        if not steps:
            return f"Task: {task}. No steps provided."

        # Join all steps into one readable sentence.
        step_list = "; ".join(steps)
        return f"Task: {task}. Steps: {step_list}"

    @staticmethod
    def _determine_action(julie_result: JulieResult) -> str:
        """Determine the action from Julie's plan.

        Scans all plan steps against the explicit SUPPORTED_ACTIONS
        mapping using whole-word regex matching.
        """
        steps = julie_result.plan

        if not steps:
            return ""

        return _resolve_action(steps)

    @staticmethod
    def _build_arguments(julie_result: JulieResult) -> dict[str, Any]:
        """Build executor arguments from Julie's result."""
        # Pass the original request and Julie's reasoning to the executor as context.
        return {
            "expanded_task": julie_result.expanded_task,
            "plan": julie_result.plan,
            "uncertainty": julie_result.uncertainty,
            "user_request": julie_result.user_request,
        }

    @staticmethod
    def _action_from_requirements(annie_result: AnnieResult) -> str:
        """Resolve an action name from Annie's requirements.

        Scans all requirements against the explicit SUPPORTED_ACTIONS
        mapping using whole-word regex matching.
        """
        return _resolve_action(annie_result.requirements)

    @staticmethod
    def _build_arguments_from_annie(annie_result: AnnieResult) -> dict[str, Any]:
        """Build executor arguments from Annie's result."""
        return {
            "user_request": annie_result.user_request,
            "interpretation": annie_result.interpretation,
            "requirements": annie_result.requirements,
            "constraints": annie_result.constraints,
            "technical_handoff": annie_result.technical_handoff,
            "clarification_needed": annie_result.clarification_needed,
        }
