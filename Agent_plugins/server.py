# this program is used in agent container, and listens only on sandbox net
# only incoming not outgoing networks

import os
from fastapi import FastAPI
from pydantic import BaseModel
from playwright.sync_api import sync_playwright

# initialising the app with variable!
app = FastAPI()

# HARDCODED values of variable
PROXY_HOST = os.environ.get("PROXY_HOST", "mitm-proxy")
PROXY_PORT = os.environ.get("PROXY_PORT", "8080")
PROXY_SERVER = f"http://{PROXY_HOST}:{PROXY_PORT}"

# creatuing a class for BROWSER request
class BrowserRequest(BaseModel):
    url :str

@app.post("/browse")
# this function is used to monitor the browser request at sametime gives the agent result
def browse(req:BrowserRequest):
    with sync_playwright as p:
        browser = p.chromium.launch(proxy = {"server": PROXY_SERVER})
        page = browser.new_page()
        page.goto(req.url, wait_until = "load", timeout = 30000)
        title = page.title()
        text = page.inner_text("body")[:3000]
        browser.close()
    return {"url":req.url, "title": title, "text":text }

@app.get("/health")
# this function is used to check the task health 
def health():
    return {"status":"ok"}