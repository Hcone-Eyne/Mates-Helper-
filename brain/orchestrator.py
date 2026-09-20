# this function is the orchestrator, like connecting the llm like chatgpt claude etc..

# note to me: this file acts like the brain router for the assistant. it decides when to answer directly and when to call tools.
# talks to llm whichever is choosen, for now anthropic supports all the function and later all other functions will be added for chatgpt and other llms

# importing the nessary modules!
import os

import anthropic

from brain.tools import TOOLS, dispatcher

# additional imports for provider option so user can use it
from agent.ollama.ollama_agent import FoxAgent
from agent.ollama.ollama_agent import OllamaFoxAgent
from agent.fox.runtime.runtime import build_runtime

# status of the provider
CURRENT_PROVIDER = "ollama"


# note: this prompt tells the model how to behave and when to use tools.
# System prompt, so claude knows
SYSTEM_PROMPT = (
    "You are a Personal Assistant and task-managing agent. You have a sandboxed browser "
    "(via the browse tool) and finance/schedule tools. Use tools when a task "
    "needs them; otherwise just answer directly. Keep replies short."
)

CURRENT_PROVIDER = "ollama"
CURRENT_THINK = False
_CURRENT_MODEL = None

def get_model():
    return _CURRENT_MODEL


def set_model(model):
    global _CURRENT_MODEL
    _CURRENT_MODEL = model

def get_think():
    return CURRENT_THINK

def set_think(value:bool):
    global CURRENT_THINK
    CURRENT_THINK = value
    return f"[Fox]: Thinking mode {'enabled' if value else 'disabled'}."

def get_provider(provider: str | None = None) -> str:
    """Return the active provider name or the requested provider name."""
    if provider is None:
        return CURRENT_PROVIDER
    return provider.lower()


def set_provider(provider: str) -> str:
    """Set the active provider and return a friendly confirmation message."""
    normalized = (provider or "").strip().lower()
    if normalized not in {"ollama", "anthropic"}:
        return "[Fox]: Unsupported provider. Please choose 'ollama' or 'anthropic'."

    global CURRENT_PROVIDER
    CURRENT_PROVIDER = normalized
    return f"[Fox]: Provider set to {CURRENT_PROVIDER}."


# note: these basic commands are local shortcuts that work even before the model is called.
# this function returns the built-in local command list
def list_commands() -> list[str]:
    return ["/help", "/status", "/ping", "/tools", "/quit"]


# note: this keeps the assistant responsive for quick checks without waiting on a model response.
# this function handles small local commands before the LLM is called
def handle_basic_command(task_description: str):
    text = (task_description or "").strip()
    if not text:
        return "[Fox]: Empty Task, Nothin to Show....."

    normalized = text.lower()
    if normalized in {"help", "/help", "cmds", "commands"}:
        return "[Fox]: Available commands: /help, /status, /ping, /tools, /quit"
    if normalized in {"status", "/status"}:
        return "[Fox]: Orchestrator is online. Anthropic model ready and local tools are loaded."
    if normalized in {"ping", "/ping"}:
        return "[Fox]: pong"
    if normalized in {"tools", "/tools"}:
        tool_names = ", ".join(tool["name"] for tool in TOOLS)
        return f"[Fox]: Available tools: {tool_names}"
    if normalized in {"quit", "/quit", "exit"}:
        return "[Fox]: Command mode closed. The orchestrator is still ready for a new task."
    return None


def _get_anthropic_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set. Use the Ollama provider or set the key.")
    return anthropic.Anthropic(api_key=api_key)


# note: this is the main agent loop — it sends the task, runs tools when needed, and keeps the conversation alive until the model stops asking for tool calls.
# this function will run the task provided by llm and agent will execute it
def run_task(task_description: str, provider: str | None = None):
    provider_name = get_provider(provider)

    local_cmd = handle_basic_command(task_description)
    if local_cmd is not None:
        return local_cmd

    if provider_name == "ollama":
        runtime = build_runtime(model=get_model(), think=get_think(), target_dir=".")
        agent = FoxAgent(runtime=runtime)
        return agent.ask(task_description)

    if provider_name == "anthropic":
        try:
            client = _get_anthropic_client()
        except RuntimeError:
            return FoxAgent().ask(task_description)

        messages = [{"role": "user", "content": task_description}]

        while True:
            response = client.messages.create(
                model="claude-sonnet-5",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                return "".join(b.text for b in response.content if getattr(b, "type", None) == "text")

            messages.append({"role": "assistant", "content": response.content})

            tool_result = []
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    result = dispatcher(block.name, block.input)
                    tool_result.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )
            messages.append({"role": "user", "content": tool_result})

    return f"[Fox]: Provider '{provider_name}' is not configured yet."
