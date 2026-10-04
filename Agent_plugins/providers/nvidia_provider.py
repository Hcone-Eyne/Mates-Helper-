# this program is to connect local agent WITH NVIDIA!

# Importing NEssary Modules!
import os
from . import openai_provider

# again this is used for local agent to connect with bigger llm for advice!
# (NVIDIA speaks the OpenAI chat-completions API, so this reuses the
# existing openai_provider implementation instead of duplicating it.)
def chat(prompt):
    return openai_provider.chat(
        prompt, 
        api_key = os.environ["NVIDIA_API_KEY"],
        base_url = "https://integrate.api.nvidia.com/v1",
        model = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
    )