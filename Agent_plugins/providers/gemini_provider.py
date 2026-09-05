# this program is to connect local agent WITH now gemini!

# importing nessary modules
import os
import requests

# this function AGAIN CONNECT WITH LOCAL AI TO GEMINI!
def chat(prompt):
    api_key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    url =  (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    resp = requests.post(
        url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60
    )

    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]