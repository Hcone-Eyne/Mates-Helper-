# Julie - This program is used to for reasoning and planing based on user prompt.....
# She doesn't execute tools or access the file just reasoning and planing so it be easier for rest of the club members who implement what user said.....

# importing nessary modules
import json
from dataclasses import dataclass
from typing import Any, Protocol

# creating a class for reasoning
class ReasoningBackend(Protocol):
    def generate(self, messages: list[dict[str, str]]) -> str:
        ...

# creating this class for ollama, like temp backend for julie
class OllamaReasoningBackend:
    # again initialising starts
    def __init__(self, client: Any):
        self.client = client

    # function responsible for GEneration!
    def generate(self, messages: list[dict[str, str]]) -> str:
        response = self.client.chat(messages)

        if not isinstance(response, dict):
            raise RuntimeError("[Julie]: Invalid response from reasoning backend.")

        message = response.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("[Julie]: Invalid response from reasoning backend.")

        content = message.get("content")
        if not isinstance(content, str):
            raise RuntimeError("[Julie]: Invalid response from reasoning backend.")
        return content


@dataclass(frozen=True)
class JulieResult:
    user_request: str
    context: str | None
    expanded_task: str
    plan: list[str]
    uncertainty: list[str]
    raw_response: str

# creating class for julie
class Julie:
    SYSTEM_PROMPT = """
    You are Julie, the reasoning agent inside Mates Helper.

    Your responsibility is to:
    - understand the task
    - expand the task into a precise objective
    - produce a concrete, ordered plan
    - identify uncertainty when necessary

    You do not execute tools.
    You do not access the filesystem.
    You do not browse the internet.
    You do not perform external actions.

    Return ONLY valid JSON matching this schema:
    {
      "expanded_task": "A precise restatement of the task",
      "plan": ["Ordered step 1", "Ordered step 2"],
      "uncertainty": ["Unknown or ambiguous point"]
    }

    Use an empty array when there is no uncertainty. Do not include markdown
    fences or any additional keys.
    """.strip()

    # again initialise 
    def __init__(self, backend: ReasoningBackend):
        self.backend = backend

    # this hendles the reasoning
    def reason(
        self, user_input: str, context: str | None = None
    ) -> JulieResult | str:
        # check for user input
        if not isinstance(user_input, str):
            raise TypeError("[Julie]: User input must be a string. ")

        user_input = user_input.strip()

        # else return the input
        if not user_input:
            return ""

        if context is not None and not isinstance(context, str):
            raise TypeError("[Julie]: Context must be a string or None.")

        context = context.strip() if context else None

        # message structure
        messages = [
            {
                "role": "system",
                "content": self.SYSTEM_PROMPT
            }
        ]

        # Context is optional, but the user request is always sent.
        if context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Context:\n{context}",
                }
            )
        messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        raw_result = self.backend.generate(messages)

        # this condition listen for backend
        if not isinstance(raw_result, str):
            raise TypeError(
                "[Julie]: Backend must return a string....."
            )

        result = self._parse_result(raw_result)
        return JulieResult(
            user_request=user_input,
            context=context,
            expanded_task=result["expanded_task"],
            plan=result["plan"],
            uncertainty=result["uncertainty"],
            raw_response=raw_result,
        )

    @staticmethod
    def _parse_result(raw_result: str) -> dict[str, Any]:
        """Parse and validate Julie's structured response."""
        content = raw_result.strip()
        if content.startswith("```") and content.endswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1]).strip()
            if content.lower().startswith("json\n"):
                content = content[5:].lstrip()

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("[Julie]: Backend returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise ValueError("[Julie]: Backend JSON must be an object.")

        required = ("expanded_task", "plan", "uncertainty")
        if any(key not in payload for key in required):
            raise ValueError(
                "[Julie]: Backend JSON is missing a required field."
            )
        if set(payload) != set(required):
            raise ValueError("[Julie]: Backend JSON contains unknown fields.")

        expanded_task = payload["expanded_task"]
        plan = payload["plan"]
        uncertainty = payload["uncertainty"]
        if (
            not isinstance(expanded_task, str)
            or not expanded_task.strip()
            or not isinstance(plan, list)
            or not all(isinstance(step, str) and step.strip() for step in plan)
            or not isinstance(uncertainty, list)
            or not all(
                isinstance(item, str) and item.strip() for item in uncertainty
            )
        ):
            raise ValueError("[Julie]: Backend JSON has invalid field types.")

        return {
            "expanded_task": expanded_task.strip(),
            "plan": [step.strip() for step in plan],
            "uncertainty": [item.strip() for item in uncertainty],
        }

    