# Fox - this program is to create a orchestrator, for julie, selina and gwen

# Fox responsibility are recieve user requests, coordinate runtime, route work between julie, selina and gwen
# and returns the final value

# importing nessary modules
from typing import Any

# create a class for fox.....
class Fox:
    "this class used to cordinate the task between fox club!"

    # start of initialisation 
    def __init__(self, runtime: Any = None):
        self.runtime = runtime

    # create a runtime property for fox
    def attach_runtime(self, runtime: Any):
        self.runtime = runtime

    # creating this function to process user request through fox club
    # TODO: Runtime isn't added yet
    def ask(self, user_input: str):

        # check for user input
        if not isinstance(user_input, str):
            raise TypeError("[Fox]: User Input must be string.....")

        if not user_input:
            return ""

        # checking for runtime
        if self.runtime is None:
            raise RuntimeError("[Fox]: Runtime isn't running yet.....")

        return self.runtime.handle(user_input)

    
