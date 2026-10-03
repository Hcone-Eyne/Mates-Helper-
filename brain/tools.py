# this program is like a menu, so agent can see and use them like kitchen utinsels

# importing nessary modules!
import os
import requests

# Hardcoded variables!
AGENT_HOST = os.environ.get("AGENT_HOST", "agent")
AGENT_PORT = os.environ.get("AGENT_PORT", "9000")

# list of tools
TOOLS = [
    {
        "name": "browse",
        "description": "Load a URL in the sandboxed browser and return its title and visible text.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "URL to load"}},
            "required": ["url"],
        },
    },
    {
        "name": "finance_calculate",
        "description": "Evaluate a math expression using Connectivity_A's operation_finder.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    },
    {
        "name": "schedule_view",
        "description": "Look up the current class/schedule entry for a given day or keyword.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
]

# this function is like a bridge of agent and tools using this agent can use those tools!
def dispatcher(tool_name: str, tool_input: dict):
    # Lazily import the agent tool registry: it pulls in pandas, which the
    # schedule/finance tools need but the browse-only path does not.
    from agent.ollama import tools as agent_tools

    # conditions based on tools and actions!
    if tool_name == "browse":
        resp = requests.post(
            f"http://{AGENT_HOST}:{AGENT_PORT}/browse",
            json = {"url": tool_input["url"]},
            timeout = 35
        )
        resp.raise_for_status()
        data = resp.json()
        return f"Title: {data['title']}\n\n{data['text']}"

    if tool_name == "finance_calculate":
        # Reuses the agent-side implementation (operation_finder + memory)
        # instead of returning a placeholder.
        return agent_tools.dispatch(
            "finance_calculate",
            expression=tool_input.get("expression", ""),
        )

    if tool_name == "schedule_view":
        # A query routes to schedule_ask; no query means "show everything".
        query = str(tool_input.get("query") or "").strip()
        if query:
            return agent_tools.dispatch("schedule_ask", query=query)
        return agent_tools.dispatch("schedule_view")

    # other option if those conditions aren't satisfied.....
    return f"Unknown tool: {tool_name}"