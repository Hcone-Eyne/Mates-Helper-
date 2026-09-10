# this program us used like a bridge of code / user to ollama

# import the nessary module
from .client import OllamaClient

# setting up the Main Prompt aka System Prompt
SYSTEM_PROMPT = """
You are Fox, the local AI agent inside Mates Helper.

You are running locally through Ollama.

Your job is to help the user with practical day-to-day tasks.

Be concise, accurate, and honest.

Do not claim that you performed an action unless a tool actually performed it.
"""

# create a class for Fox, Turn it into Fox - AGENT!
class FoxAgent:

    # creating the constructor!
    def __init__(self, model = None):
        self.client = OllamaClient(model = model) # calling another class to make it up!

        self.messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

    # this function is like a query
    def ask(self, user_input):
        self.messages.append(
            {
                "role": "user",
                "content": user_input
            }
        )

        response = self.client.chat(self.messages)
        message = response["message"]
        self.messages.append(message)

        return message.get("content", "")

    @property
    def model(self):
        return self.client.model