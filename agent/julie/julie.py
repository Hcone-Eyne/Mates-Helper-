# Julie - This program is used to for reasoning and planing based on user prompt.....
# She doesn't execute tools or access the file just reasoning and planing so it be easier for rest of the club members who implement what user said.....

# importing nessary modules
from typing import Any, Protocol

# creating a class for reasoning
class ReasoningBackend(Protocol):
    def generate(self, messages: list[dict[str, str]]):
        ...

# creating this class for ollama, like temp backend for julie
class OllamaReasoningBackend():
    # again initialising starts
    def __init__(self, client: Any):
        self.client = client

    # function responsible for GEneration!
    def geenrate(self, messages: list[dict[str, str]]):
        response = self.client.chat(messages)

        # conditions for checking the response
        try:
            return response ["message"]["content"]
        except (KeyError, TypeError) as e:
            raise RuntimeError("[Julie]: Invalid response from reasoning backend.") from e

# creating class for julie
class Julie:
    SYSTEM_PROMPT = """
    You are Julie, the reasoning agent inside Mates Helper.

    Your responsibility is to:
    - understand the task
    - reason about the problem
    - produce a clear plan or proposed solution
    - identify uncertainty when necessary

    You do not execute tools.
    You do not access the filesystem.
    You do not browse the internet.
    You do not perform external actions.

    Return reasoning output for the other Fox Club components.
    """.strip()

    # again initialise 
    def __init__(self, backend: ReasoningBackend):
        self.backend = backend

    # this hendles the reasoning
    def reason(self, user_input, context: str | None):
        # check for user input
        if not isinstance(user_input, str):
            raise TypeError("[Julie]: User input must be a string. ")

        user_input = user_input.strip()

        # else return the input
        if not user_input:
            return ""

        # message structure
        messages = [
            {
                "role": "system",
                "content": self.SYSTEM_PROMPT
            }
        ]

        # this is ment to sent the content to julie!
        if context:
            messages.append[
                {
                    "role": "system",
                    "content": f"Context:\n(context)"
                }
            ]
            messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        result = self.backend.generate(messages)

        # this condition listen for backend
        if not isinstance(result, str):
            raise TypeError(
                "[Julie]: Backend must return a string....."
            )

        return result.strip()
    