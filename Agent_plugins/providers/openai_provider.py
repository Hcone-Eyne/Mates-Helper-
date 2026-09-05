# this program is used to access openai model AKA CHATGPT!

# importing nessary modules
import os
from . import openai_compatible


# this function is used to connect Chatgpt to local Agent for Suggestion incase if agent stuck.....
def chat(prompt):
    return openai_compatible.chat(
        prompt, 
        api_key = os.environ["OPENAI_API_KEY"],
        base_url = "https://api.openai.com/v1",
        model = os.environ.get("OPENAI_MODEL", "gpt-5")
    )
