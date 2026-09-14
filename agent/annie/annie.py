# Annie - She is like an Manager, Gives correct task and clarify Club Member doubts!
# she is like a Team lead for selina..

# like julie -> annie -> selina and then later refinement function annie-> selina -> gwen if mistake happens, gwen -> annie -> selina!


# importing the nessary modules
import json
from dataclasses import dataclass
from typing import Any, Protocol

# external import
from agent.julie.julie import JulieResult

# Creating a class for annie_backend
class AnnieBackend(Protocol):
    # this function generates Annie's structured handoff response
    def generate(self, messages: list[dict[str, str]]) -> str:
        ...

# this class is for ollama connection and annie
class OllamaAnnieBackend:
    # this function initializes the Ollama client used by Annie
    def __init__(self, client: Any):
        self.client = client

    # this function sends Annie's prompt to Ollama and returns its text
    def generate(self, messages: list[dict[str, str]]) -> str:
        response = self.client.chat(messages)

        try:
            # this checks that Ollama returned the expected message structure
            content = response["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(
                "[Annie]: Invalid response received from Ollama....."
            ) from exc

        # this checks that Ollama returned text instead of another data type
        if not isinstance(content, str):
            raise RuntimeError(
                "[Annie]: Invalid response received from Ollama....."
            )
        return content
    
@dataclass(frozen = True)
# this class stores Annie's structured handoff for the other agents
class AnnieResult:
    user_request: str
    interpretation: str
    requirements: list[str]
    constraints: list[str]
    technical_handoff: str
    clarification_needed: list[str]
    raw_response: str

# main annie class
class Annie:
    # annie's system prompt
    SYSTEM_PROMPT = """
You are Annie, a semantic software engineer in Fox Club.

Your job is to receive Julie's reasoning and turn it into a
clear engineering handoff for Selina.

Your responsibilities:
1. Understand the user's actual intent.
2. Structure the task clearly.
3. Separate requirements from constraints.
4. Identify missing information.
5. Explain what Selina needs to accomplish technically.
6. Preserve uncertainty instead of inventing user preferences.
7. Do not invent facts.
8. Do not execute commands.
9. Do not access files, directories, browsers, APIs, or external tools.
10. Do not generate arbitrary shell commands as the primary output.

You and Selina are peer engineers with different perspectives.

Annie owns:
- semantics
- requirements
- intent
- task structure
- ambiguity

Selina owns:
- technical interpretation
- implementation
- commands
- tools
- filesystem operations
- execution

Your handoff must therefore describe WHAT needs to happen,
not pretend to already know HOW every technical operation will happen.

If Selina later reports that your interpretation is technically
ambiguous or incorrect, you should be able to refine your interpretation.

IMPORTANT:
- Missing user preferences are uncertainties, not errors.
- Do not invent folder structures, filenames, paths, or commands
  unless they are explicitly provided.
- A future step in Julie's plan is not considered completed merely
  because it exists in the plan.

Return ONLY valid JSON.

Required format:

{
  "interpretation": "...",
  "requirements": ["..."],
  "constraints": ["..."],
  "technical_handoff": "...",
  "clarification_needed": ["..."]
}
""".strip()

    # this function initializes Annie with the selected reasoning backend
    def __init__(self, backend: AnnieBackend):
        self.backend = backend

    # this function converts Julie's reasoning into an engineering handoff
    def structure(self, julie_result: JulieResult) -> AnnieResult:
        # this checks that Annie received Julie's expected result type
        if not isinstance(julie_result, JulieResult):
            raise TypeError(
                "[Annie]: Expected a JulieResult."
            )

        # this validates the request before building Annie's prompt
        if not isinstance(julie_result.user_request, str):
            raise TypeError(
                "[Annie]: Julie user_request must be a string."
            )

        if not julie_result.user_request.strip():
            raise ValueError(
                "[Annie]: Cannot structure an empty user request."
            )

        # this builds the user message from Julie's complete reasoning
        user_message = self._build_user_message(julie_result)

        # this asks the backend to create the handoff
        raw_response = self.backend.generate(
            [
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ]
        )


        # this validates and extracts Annie's JSON response
        parsed = self._parse_response(raw_response)

        # this returns the handoff together with the original backend response
        return AnnieResult(
            user_request=julie_result.user_request,
            interpretation=parsed["interpretation"],
            requirements=parsed["requirements"],
            constraints=parsed["constraints"],
            technical_handoff=parsed["technical_handoff"],
            clarification_needed=parsed["clarification_needed"],
            raw_response=raw_response,
        )

    # this function refines Annie's handoff using Selina's technical feedback
    def refine(
        self,
        previous_result: AnnieResult,
        selina_feedback: str,
    ) -> AnnieResult:
        # this checks that refinement starts from a valid Annie result
        if not isinstance(previous_result, AnnieResult):
            raise TypeError(
                "[Annie]: Expected an AnnieResult."
            )

        # this validates Selina's feedback before sending it to the backend
        if not isinstance(selina_feedback, str):
            raise TypeError(
                "[Annie]: Selina feedback must be a string."
            )

        if not selina_feedback.strip():
            raise ValueError(
                "[Annie]: Selina feedback cannot be empty."
            )

        # this combines the old handoff with Selina's feedback for refinement
        user_message = f"""
        Previous Annie interpretation:

        {json.dumps(
            {
                "interpretation": previous_result.interpretation,
                "requirements": previous_result.requirements,
                "constraints": previous_result.constraints,
                "technical_handoff": previous_result.technical_handoff,
                "clarification_needed": previous_result.clarification_needed,
            },
            indent=2,
        )}

        Selina's technical feedback:

        {selina_feedback}

        Refine the interpretation only where necessary.

        Return the corrected engineering handoff using the exact JSON format.
        """.strip()

        # this asks the backend to produce the corrected handoff
        raw_response = self.backend.generate(
            [
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ]
        )

        # this parses the new response before constructing the refined result
        parsed = self._parse_response(raw_response)

        # this preserves the original user request during refinement
        return AnnieResult(
            user_request=previous_result.user_request,
            interpretation=parsed["interpretation"],
            requirements=parsed["requirements"],
            constraints=parsed["constraints"],
            technical_handoff=parsed["technical_handoff"],
            clarification_needed=parsed["clarification_needed"],
            raw_response=raw_response,
        )

    @staticmethod
    # this function is responsible for user message passing user message
    def _build_user_message(julie_result: JulieResult) -> str:
        # this formats Julie's request and plan for Annie's backend
        return f"""
        User request: 
        {julie_result.user_request} 

        Julie's expanded task:
        {julie_result.expanded_task}

        Julie's plan:
        {json.dumps(julie_result.plan, indent=2)}
        
        Structure this into an engineering handoff for selina
        """.strip()

    @staticmethod
    # this function parses and validates Annie's JSON response
    def _parse_response(raw_response: str) -> dict[str, Any]:
        # this checks that the backend returned text
        if not isinstance(raw_response, str):
            raise TypeError("[Annie]: Backend response must be a string..... ")

        text = raw_response.strip()

        # this removes optional markdown fences around JSON responses
        if text.startswith("```"):
            lines = text.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            text = "\n".join(lines).strip()
            if text.lower().startswith("json\n"):
                text = text[5:].lstrip()

        # this converts the backend text into a Python object
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("[Annie]: Backend returned invalid json.....") from exc

        # this ensures the JSON root is an object with named fields
        if not isinstance(data, dict):
            raise ValueError("[Annie]: Excepted a Json.....")

        required_keys = {
            "interpretation",
            "requirements",
            "constraints",
            "technical_handoff",
            "clarification_needed",
        }

        missing = required_keys - data.keys()

        # this rejects incomplete handoffs before any fields are used
        if missing:
            raise ValueError(
                f"[Annie]: Missing required fields: {sorted(missing)}"
            )

        # this validates the two text fields
        if not isinstance(data["interpretation"], str):
            raise TypeError(
                "[Annie]: interpretation must be a string."
            )

        if not isinstance(data["technical_handoff"], str):
            raise TypeError(
                "[Annie]: technical_handoff must be a string."
            )

        # this validates the three list fields
        if not isinstance(data["requirements"], list):
            raise TypeError(
                "[Annie]: requirements must be a list."
            )

        if not isinstance(data["constraints"], list):
            raise TypeError(
                "[Annie]: constraints must be a list."
            )

        if not isinstance(data["clarification_needed"], list):
            raise TypeError(
                "[Annie]: clarification_needed must be a list."
            )

        # this ensures every list item can be safely consumed as text
        for field in (
            "requirements",
            "constraints",
            "clarification_needed",
        ):
            if not all(isinstance(item, str) for item in data[field]):
                raise TypeError(
                    f"[Annie]: {field} must contain only strings."
                )

        return data
