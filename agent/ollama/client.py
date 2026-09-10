# this program handles the communication with ollama directly!

# importing the nessary modules
import json
import urllib.request
import urllib.error

from .discovery import discover_ollama

# creating a class!
class OllamaClient:

    # setting up the constructor!
    def __init__(self, host = None, model = None):
        info = discover_ollama()

        self.host = (host or info["host"]).rstrip("/")
        self.model = model

        if not self.model:
            self.model = self._select_model(info["models"])

    # this function is met to choose a model
    def _select_model(self, models):

        # this checks if the model is present 
        if not models:
            raise RuntimeError(
                f"[Fox]: No Ollama model is found. Pull a model first."
            )
        names = [model.get("name", "") for model in models]

        # my prefered option is hardcoded......
        for name in names:
            if "qwen2.5:3b-instruct" in name.lower():
                return name

        # else use the 1st installed model
        return names[0]
        
    # this function handles the chat
    def chat(self, messages, stream = False):

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
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
    