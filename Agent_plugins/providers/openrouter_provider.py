# this program is used to connect openrouter all models like openai providers!

# importing the nessary modules
import os
from . import openai_compatible

# this function is ment to chat with openrouter llm
def chat(prompt):
    return openai_compatible.chat(
        prompt,
        api_key = os.environ["OPENROUTER_API_KEY"],
        base_url = "https://openrouter.ai/api/v1",
        model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o")
    )
