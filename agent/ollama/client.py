# this program handles the communication with ollama directly!

# importing the nessary modules
import os
import json
import urllib.request
import urllib.error

from .discovery import discover_ollama

# creating a class!
class OllamaClient:

    # setting up the constructor!
    def __init__(self, host = None, model = None, think = False):
        info = discover_ollama()

        self.host = (host or info["host"]).rstrip("/")
        self.think = think 
        available_models = [model.get("name", "") for model in info.get("models", [])]

        if model and model in available_models:
            self.model = model
        elif model and model not in available_models:
            self.model = self._select_model(info["models"])
        else:
            self.model = os.environ.get("OLLAMA_MODEL") or self._select_model(info["models"])

    # this function is met to choose a model
    def _select_model(self, models):

        # this checks if the model is present
        if not models:
            raise RuntimeError(
                f"[Fox]: No Ollama model is found. Pull a model first."
            )

        names = [model.get("name", "") for model in models if model.get("name")]
        if not names:
            raise RuntimeError(
                f"[Fox]: No Ollama model is found. Pull a model first."
            )

        qwen_models = [name for name in names if "qwen" in name.lower()]
        if qwen_models:
            return qwen_models[0]

        return names[0]
        
    # this function handles the chat
    def chat(self, messages, stream = False, think = None):

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "think": self.think if think is None else think
        }

        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=data,
            headers={
                "Content-Type": "application/json"
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(
                    response.read().decode("utf-8")
                )

            return result
        # to catch the error
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                detail = str(e)
            raise RuntimeError(f"Ollama API error ({e.code}) at {self.host}/api/chat: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Could not connect to Ollama at {self.host}: {e}"
            ) from e

    # this function is ment to  get query from user
    def ask(self, prompt):
        response = self.chat([
            {
                "role": "user",
                "content": prompt
            }
        ])
        return response["message"]["content"]
    