# this function is the orchestrator, like connecting the llm like chatgpt claude etc..

# note to me: this file acts like the brain router for the assistant. it decides when to answer directly and when to call tools.
# talks to llm whichever is choosen, for now anthropic supports all the function and later all other functions will be added for chatgpt and other llms

# importing the nessary modules!
import os
import anthropic
from brain.tools import TOOLS, dispatcher

# note: keep the API key in environment variables so secrets are not hardcoded in the project.
# initialising claude!
client = anthropic.Anthropic(api_key = os.environ["ANTHROPIC_API_KEY"])

# note: this prompt tells the model how to behave and when to use tools.
# System prompt, so claude knows
SYSTEM_PROMPT = (
    "You are a Personal Assistant and task-managing agent. You have a sandboxed browser "
    "(via the browse tool) and finance/schedule tools. Use tools when a task "
    "needs them; otherwise just answer directly. Keep replies short."
)

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
    text = (task_description or "").strip()
    if not text:
        return None

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

# note: this fallback is a safe placeholder if another model is selected later.
# this function creates a simple local provider fallback when another model is requested
def get_provider(provider: str):
    class _FallbackProvider:
        def chat(self, task_description: str):
            return f"[Fox]: {provider} provider is not configured yet. Use the Anthropic provider or a local command."

    return _FallbackProvider()

# note: this is the main agent loop — it sends the task, runs tools when needed, and keeps the conversation alive until the model stops asking for tool calls.
# this function will run the task provided by llm and agent will execute it
def run_task(task_description: str, provider: str = "anthropic"):
    local_cmd = handle_basic_command(task_description)
    if local_cmd is not None:
        return local_cmd

    if provider != "anthropic":
        # no tool access yet for these
        return get_provider(provider).chat(task_description)

    messages = [{"role": "user", "content": task_description}]

    while True:
        response = client.messages.create(
            model = "claude-sonnet-5",
            max_tokens = 1024,
            system = SYSTEM_PROMPT,
            tools = TOOLS, 
            messages = messages
        )

        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")

        messages.append({"role": "assistant", "content": response.content})

        tool_result = []
        for block in response.content:
            if block.type == "tool_use":
                result = dispatcher(block.name, block.input)
                tool_result.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )
        messages.append({"role": "user", "content": tool_result})