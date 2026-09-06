# this program is used to access openai model AKA CHATGPT!

# importing nessary modules
import os
import requests
from . import openai_compatible


# this function is used to connect Chatgpt to local Agent for Suggestion incase if agent stuck.....
def chat(prompt, api_key, base_url, model):
    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model, 
        "messages":[{"role": "user", "content": prompt}],
    }
    resp = requests.post(url, headers = headers, json = payload, timeout = 60)
    resp.raise_for_status()
    return resp.json()["choice"][0]["message"]["content"]
