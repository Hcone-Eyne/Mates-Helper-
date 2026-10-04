# this program connet local agent / whatever ai you use, the bridge way..

# importing nessary module
import asyncio
import json
import secrets
import threading
import uuid

import websockets
from fastmcp import FastMCP
import os


# setting up mcp!
mcp = FastMCP("Fox-Agent-Gateway")

# setting up the route!
# Loopback by default: the gateway accepts a remote desktop agent, so it
# must never listen on all interfaces unless explicitly configured to.
AGENT_HOST = os.environ.get("AGENT_GATEWAY_HOST", "127.0.0.1")
AGENT_PORT = int(os.environ.get("AGENT_GATEWAY_PORT", "8765"))  
AGENT_TIMEOUT = 20  # time exceed, process is cut off instead of loop


# Name of the environment variable holding the gateway token. This follows
# the Brain API pattern: the token is server-side configuration, never
# hardcoded, never logged, never echoed back to the client.
GATEWAY_TOKEN_ENV_VAR = "FOX_API_TOKEN"

# First-message handshake timeout: an unauthenticated connection must not
# be allowed to sit half-open forever.
HANDSHAKE_TIMEOUT = 10


def _gateway_token() -> str | None:
    """Return the configured gateway token, or None when it is not set."""
    token = os.environ.get(GATEWAY_TOKEN_ENV_VAR)
    return token if token else None


def _token_is_valid(presented) -> bool:
    """Constant-time token check. Fails closed when the server token is
    missing, or when the presented value is absent/invalid."""
    configured = _gateway_token()
    if not configured or not isinstance(presented, str) or not presented:
        return False
    return secrets.compare_digest(presented, configured)


async def _close_connection(websocket, code: int, reason: str) -> None:
    try:
        await websocket.close(code=code, reason=reason)
    except Exception:
        pass


async def _read_handshake(websocket) -> bool:
    """Read and validate the first message as an auth handshake.

    Returns True only for an authenticated agent. The connection is closed
    on any failure - missing server token, malformed message, or wrong
    token. Fail closed, no retries.
    """
    try:
        raw = await asyncio.wait_for(websocket.recv(), timeout=HANDSHAKE_TIMEOUT)
    except Exception:
        await _close_connection(websocket, 4408, "handshake timeout")
        return False
    try:
        hello = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        await _close_connection(websocket, 4400, "malformed handshake")
        return False
    if not isinstance(hello, dict) or not _token_is_valid(hello.get("token")):
        await _close_connection(websocket, 4401, "unauthorized")
        return False
    return True


# these keep track of Websockets Conneection and Pending asynchronous operations.....
_agent_conn = None
_pending : dict [str, asyncio.Future] = {}
_bridge_loop : asyncio.AbstractEventLoop | None = None

# creating a websocket connection
async def _handle_agent(websocket):
    global _agent_conn
    # The connection is NOT trusted yet: the first message must carry the
    # gateway token. Only an authenticated agent becomes _agent_conn.
    if not await _read_handshake(websocket):
        return
    _agent_conn = websocket
    # this condition waits for the messaages from agent over Websocket
    try:
        async for raw in websocket:
            try:
                # agents message will be like json thi..
                msg = json.loads(raw)
            # this catchs if the agent sends invalid message like string, and it gets ignored and waits for another message
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if not isinstance(msg, dict):
                # Valid JSON but not an object (list, string, number): ignoring
                # it keeps one bad message from killing the whole handler.
                continue
            # this id tells the server which request and each response belongs to!
            req_id = msg.get("id")
            try:
                # fut = Future like messahe , and this contains all the pending query!, and none means if threre isn't an entry with id, it sliently fade instead of error
                fut = _pending.pop(req_id, None)
            except TypeError:
                # Unhashable id (list/dict): cannot match any request.
                continue
            # this check if somehtin is waiting.. 
            # checks wheather fut has already finished tasks or not
            if fut and not fut.done():
                # gives the response to whover in the list 
                fut.set_result(msg)
    # this run either everything went good or bad no matter what
    finally:
        # checks if the websocket is still connected
        if _agent_conn is websocket:
            # if yes, it means agent is no longer connected
            _agent_conn = None

# this function is going to start the bridge
def _start_bridge_loop():
    global _bridge_loop
    # creates a new loop, like an event manager loop
    loop = asyncio.new_event_loop()
    # and that loop stoed global variable for any where acess..
    _bridge_loop = loop
    # makes this lop the current event loop for this thread
    asyncio.set_event_loop(loop)

    # this kick starts the websocket server!
    async def _main():
        # it start a websocket server and host and port whenever agent connects and then call _handle_agent functioN!
        async with websockets.serve(_handle_agent, AGENT_HOST, AGENT_PORT):
            # this means keep this websocket server alive infinitily
            await asyncio.Future()
    # this gets loopes until it completed those given tasks 
    loop.run_until_complete(_main())

# the gateway thread handle (None until start_gateway runs)
_bridge_thread = None
_bridge_thread_lock = threading.Lock()


def start_gateway():
    """Start the WebSocket bridge thread (idempotent).

    Importing this module no longer starts any listener: the caller must
    start the gateway explicitly (or run this file as __main__).
    """
    global _bridge_thread
    with _bridge_thread_lock:
        if _bridge_thread is not None and _bridge_thread.is_alive():
            return _bridge_thread
        _bridge_thread = threading.Thread(
            target=_start_bridge_loop, daemon=True, name="fox-agent-gateway"
        )
        _bridge_thread.start()
        return _bridge_thread

# this function will handle calls to send to agents
# this sends cmd to connected agent and waits for response
def _send_to_agent(cmd: str, args: dict | None = None) -> dict:
    # checking if agent is present or not
    if _agent_conn is None:
        # if not, it doesn't waste time by sending request to non exists socket
        return {"ok":False, "error":"No local agent connected"}
    # checking bridge is present or not
    if _bridge_loop is None:
        # same here from the above
        return {"ok": False, "error": "Bridge not started yet....."}

    # this is used to generate a unique id
    req_id = str(uuid.uuid4())
    # this creates python dict into json 
    payload = json.dumps({"id": req_id, "cmd": cmd, "args": args or {}})

    # this is used to send async the _aend_to_agent() function
    async def _dispatch():
        # this ment like this variable is waiting for somehting big to happen
        fut = asyncio.get_event_loop().create_future()
        # stores the current req_id so it knows where to put response
        _pending[req_id] = fut
        # sends the request to ahent
        await _agent_conn.send(payload)
        # this waits for agent response
        try:
            # waits for agent to respond!
            return await asyncio.wait_for(fut, timeout = AGENT_TIMEOUT)
        # this condition is how to handle timeout
        except asyncio.TimeoutError:
            # this remove the _pending request of Fut! (which means Future request tho.....)
            _pending.pop(req_id, None)
            return {"ok": False, "error": "agent timed out"}
    # this is mento to run on websocket at event loop that is running in the background thread.....
    future = asyncio.run_coroutine_threadsafe(_dispatch(), _bridge_loop)
    # this waits for _dispatch to finish
    return future.result(AGENT_TIMEOUT + 2) 
 
 
# MCP commands exposed to the connected agent
@mcp.tool()
# this function exposes the current status of the agent
def agent_status() -> str:
    """Check whether the local desktop agent is currently connected over WebSocket."""
    return "[Fox]: Agent connected." if _agent_conn else "[Fox]: No agent connected."
 
# MCP is used to Perform action in desktop
@mcp.tool()
# this function is ment to take screenshot and sent it to mcp so Ai_agents know what's happening in the desktop
def desktop_screenshot(app_name: str = "") -> str:
    """Capture a screenshot of the desktop or a specific application window."""
    # if agent calls this, it takes an screenshot and sent to agent.....
    reply = _send_to_agent("screenshot", {"app_name": app_name})
    # this condition checks the response
    if not reply.get("ok"):
        # if something went wrong, this return the error
        return f"[Fox]: {reply.get('error', 'unknown error')}"
    return str(reply.get("result", ""))
 
 
if __name__ == "__main__":
    start_gateway()
    mcp.run()
 
        
