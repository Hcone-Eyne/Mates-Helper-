# this program is to connect local agent WITH NVIDIA!

# Importing NEssary Modules!
import os
from . import openai_compatible

# again this is used for local agent to connect with bigger llm for advice!
def chat(prompt):
    return openai_compatible.chat(
        prompt, 
        api_key = os.environ["NVIDIA_API_KEY"],
        base_url = "https://integrate.api.nvidia.com/v1",
        model = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
    )