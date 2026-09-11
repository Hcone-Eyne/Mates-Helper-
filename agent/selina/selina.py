# Selina - She is the one proceed with the tasks..
# aka have the most powerfull part in this.....

# importing the nessary modules
from dataclasses import dataclass
from typing import Any, Protocol

# this class is used to perform the task selina needs
class ActionExecutor(Protocol):
    # TODO: Finish it
    def execute(self, action:str, arguments: dict[str,str]):
        ...

@dataclass
# this function is used for to pass selina result
def SelinaResult():
    succes: bool
    action: str
    result: Any = None
    error :str |None = None

# this class is for Selina the core!
class Selina():

    # adding the initializer
    def __init__(self, executor: ActionExecutor):
        self.executor = executor

    def execute( self, action: str, arguments: dict[str, Any] | None = None):

         # validate action.
        if not isinstance(action, str):
            raise TypeError(
                "[Selina]: Action must be a string."
            )

        action = action.strip()

        if not action:
            return SelinaResult(
                success=False,
                action=action,
                error="Action is empty."
            )

        # validate arguments
        if arguments is None:
            arguments = {}

        if not isinstance(arguments, dict):
            raise TypeError(
                "[Selina]: Action arguments must be a dictionary....."
            )

        try:
            # selina pass this to ActionExecutor to proceed with the decision
            result = self.executor.execute(
                action=action,
                arguments=arguments
            )

            return SelinaResult(
                success=True,
                action=action,
                result=result
            )

        except Exception as exc:
            return SelinaResult(
                success=False,
                action=action,
                error=str(exc)
            )
