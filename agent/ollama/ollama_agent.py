# FoxAgent — local AI agent with tool-calling capability
# Bridges Qwen via Ollama to Schedule_Bot, Finance_bot, and web tools.

import re
from .client import OllamaClient
from .tools import TOOLS, dispatch, tool_prompt_block

# Maximum tool-call iterations per user message (prevents infinite loops)
MAX_TOOL_TURNS = 5

# Regex to detect tool calls in model output
# Handles variations:  >>TOOL: name(args)<<  or  >>TOOL: name(args)<>  etc.
TOOL_CALL_RE = re.compile(
    r'>>TOOL:\s*(\w+)\((.*?)\)\s*<<',
    re.DOTALL,
)

# Fallback: model wrote >>TOOL: name(args)<> or similar broken closing
TOOL_CALL_FALLBACK_RE = re.compile(
    r'>>TOOL:\s*(\w+)\((.*?)\)\s*[<>]+',
    re.DOTALL,
)

# Parse individual key="value" arguments from inside the parentheses
ARG_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def _resolve_tool_name(raw_name):
    """Best-effort match of a potentially mangled name to a registered tool.

    Handles cases like 'finance_calculateexpression' -> 'finance_calculate'
    by trying progressively shorter prefixes against the registry.
    """
    if raw_name in TOOLS:
        return raw_name
    # Try removing trailing characters that might be a fused parameter name
    for length in range(len(raw_name) - 1, 2, -1):
        candidate = raw_name[:length]
        if candidate in TOOLS:
            return candidate
    return raw_name  # will produce "Unknown tool" in dispatch


def _parse_tool_calls(text):
    """Extract all tool calls from model output.

    Returns a list of dicts: [{"name": ..., "args": {...}}, ...]
    """
    calls = []
    # Try primary regex first, then fallback
    matches = list(TOOL_CALL_RE.finditer(text))
    if not matches:
        matches = list(TOOL_CALL_FALLBACK_RE.finditer(text))

    for match in matches:
        raw_name = match.group(1)
        raw_args = match.group(2)
        name = _resolve_tool_name(raw_name)
        args = {}
        for m in ARG_RE.finditer(raw_args):
            args[m.group(1)] = m.group(2)
        calls.append({"name": name, "args": args})
    return calls


def _strip_tool_calls(text):
    """Remove tool-call lines from the model's text, leaving only the conversational part."""
    text = TOOL_CALL_RE.sub("", text)
    text = TOOL_CALL_FALLBACK_RE.sub("", text)
    return text.strip()


# ---------------------------------------------------------------------------
# System Prompt  (built once at import time)
# ---------------------------------------------------------------------------

_BASE_PROMPT = """\
You are Fox, the local AI agent inside Mates Helper.
You are running locally through Ollama.

Your job is to help the user with practical day-to-day tasks.
Be concise, accurate, and honest.

RULES:
- You have access to tools. Use them when a task requires real data.
- To use a tool, write a single line in this exact format:
    >>TOOL: tool_name(param1="value1", param2="value2")<<
- You MUST wait for the tool result before claiming any action was performed.
- Never fabricate tool results. If a tool fails, say so honestly.
- You may call multiple tools in sequence if needed.
- After receiving tool results, give the user a clear, final answer.
"""

def _build_system_prompt():
    tool_block = tool_prompt_block()
    if tool_block:
        return _BASE_PROMPT + "\nAVAILABLE TOOLS:\n" + tool_block
    return _BASE_PROMPT


# ---------------------------------------------------------------------------
# FoxAgent Class
# ---------------------------------------------------------------------------

class FoxAgent:
    """Local AI agent with tool-calling loop.

    Usage:
        agent = FoxAgent()
        response = agent.ask("what's my schedule today?")
    """

    def __init__(self, model=None):
        self.client = OllamaClient(model=model)
        self.system_prompt = _build_system_prompt()
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]

    def ask(self, user_input):
        """Send a message and return the final text response.

        Handles the tool-use loop internally: if the model requests a tool,
        it is executed and the result fed back, up to MAX_TOOL_TURNS times.
        """
        self.messages.append({"role": "user", "content": user_input})

        for turn in range(MAX_TOOL_TURNS):
            try:
                response = self.client.chat(self.messages)
            except Exception as e:
                return f"[Fox]: Could not reach Ollama — {e}"

            message = response["message"]
            content = message.get("content", "")

            # Check for tool calls in the model's output
            tool_calls = _parse_tool_calls(content)

            if not tool_calls:
                # No tool calls — this is the final answer
                self.messages.append(message)
                return content

            # Model requested tools: execute them and feed results back
            self.messages.append(message)

            for call in tool_calls:
                tool_name = call["name"]
                tool_args = call["args"]
                result = dispatch(tool_name, **tool_args)

                tool_result_msg = (
                    f"[Tool Result — {tool_name}]\n{result}"
                )
                self.messages.append({
                    "role": "tool",
                    "content": tool_result_msg,
                })

        # If we exhausted MAX_TOOL_TURNS, return whatever the model last said
        return content + "\n\n[Fox]: Hit tool-call limit, stopping here."

    @property
    def model(self):
        return self.client.model
