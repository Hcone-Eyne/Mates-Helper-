# Selina - She is the one proceed with the tasks..
# aka have the most powerfull part in this.....

# importing the nessary modules
from dataclasses import dataclass
from typing import Any, Protocol

from agent.julie.julie import JulieResult

# this class is used to perform the task selina needs
class ActionExecutor(Protocol):
    # Every executor must provide this method so Selina can run an action.
    def execute(self, action: str, arguments: dict[str, Any]) -> Any:
        ...

@dataclass
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

        Uses the first step as the action name.
        This is a simple heuristic — can be extended later.
        """
        # Julie's first step is treated as the command to run.
        steps = julie_result.plan

        # No steps means there is no command to execute.
        if not steps:
            return ""

        # Normalize the command for executor lookup, such as "Run Tests" -> "run_tests".
        return steps[0].strip().lower().replace(" ", "_")

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
