# this is the place where the agent logic showns

# we are going to use mitm-proxy which is going to handle connection on the network!
# the interesting think about the name is MIM = Man in Middle.....

""" Agent can open browser, 
routed through server with rules like, 
network level monitoring so agent can't break them i hope so"""

# importing nessary Modules
import os
from playwright.sync_api import sync_playwright

# hardcoded values for the proxy settings
PROXY_HOST = os.environ.get("PROXY_HOST", "mitm-proxy")
PROXY_PORT = os.environ.get("PROXY_PORT", "8080")
PROXY_SERVER = f"http://{PROXY_HOST}:{PROXY_PORT}"

# this function handles the agent current task
def run_task(page, task: str):
    """Placeholder for actual agent task logic — replace with your
    message-app dispatch (LLM decides the action, this executes it)."""

    page.goto(task)
    print(f"[Agent]: loaded: {page.title()}")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(proxy = {"server": PROXY_SERVER})
        page = browser.new_page()

        run_task(page)

        browser.close()

if __name__ == "__main__":
    main()