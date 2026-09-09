# this program is going to auto detech the ollama server and other belongs.....

# importing the nessary modules
import os
import shutil
import urllib.request
import urllib.error
import json

# get the discovery connection for ollama
DEFAULT_HOST = "http://127.0.0.1:11434"

# this function finds the ollama nessary dependicies
def find_ollama_binary():
    return shutil.which("ollama")

# this function is to get the host of ollama!
def get_ollama_host():
    return shutil.which("ollama")

# this function is to check the server status
def check_server(host:str) -> bool:

    # this condition checks for statement
    try:
        request = urllib.request.Request(
            f"(host)/api/tags",
            method = "GET"
        )

        with urllib.request.urlopen(request, timeout = 2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False

# this function fetch the available model.....
def get_models(host:str):
    # ask ollama
    request = urllib.request.Request(
        f"{host}/api/tags",
        method = "GET"
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))

    return data.get("models", [])

# this function is going to auto detct ollama so no mess while setting up
def discover_ollama():

    # ollama required variable to find them.....
    binary = find_ollama_binary()
    host = get_ollama_host()

    # see for server status
    server_running = check_server(host)

    # get the available model list
    models = []

    # conditions if server is running!
    if server_running:
        try:
            models = get_models(host)
        except Exception:
            models = []

        return {
        "installed": binary is not None,
        "binary": binary,
        "host": host,
        "running": server_running,
        "models": models,
    }