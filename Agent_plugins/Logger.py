# this program is used to log what the agent does

# mitmproxy - this is used to record every action of agent 
# Runs inside the mitm-proxt contanitr only..
# Agent has no mount, no credientials and no route to this file!


# importing nessaary modules
import json
import time
from mitmproxy import http

# This is log storer path
LOG_PATH = "/logs/traffic.jsonl"

# this function handles the response of the agent!
def response(flow: http.HTTPFlow):
    # entry of the agent!
    entry = {
        "timestamp" : time.time(),
        "method" : flow.request.method,
        "url": flow.request.pretty_url,
        "status_code": flow.response.status_code if flow.response else None, 
        "request_headers": dict(flow.request.headers),
        "request_body_size": len(flow.request.raw_content or b""),
        "response_body_size": len(flow.response.raw_content or b"") if flow.response else 0,
    }

    # this will write the report to the log path
    with open(LOG_PATH, "a") as f:
        f.write(json.dump(entry) + "\n")

def error(flow:http.HTTPFlow):
    # this is the structure of the entry!
    entry = {
        "timestamp": time.time(),
        "method": flow.request.method,
        "url": flow.request.pretty_url,
        "error": str(flow.error),
    }

    # error gets loged into the report!
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
