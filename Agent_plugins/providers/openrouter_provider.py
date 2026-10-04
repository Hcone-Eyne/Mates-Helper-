# this program is used to connect openrouter all models like openai providers!

# importing the nessary modules
import os
from . import openai_provider

# this function is ment to chat with openrouter llm
# (OpenRouter speaks the OpenAI chat-completions API, so this reuses the
# existing openai_provider implementation instead of duplicating it.)
def chat(prompt):
    return openai_provider.chat(
        prompt,
        api_key = os.environ["OPENROUTER_API_KEY"],
        base_url = "https://openrouter.ai/api/v1",
        model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o")
    )
