"""Focused security tests for mcp_plugins/local_agent_gateway.py.

Covers the P1-2 hardening: loopback-by-default binding, no listener on
import, FOX_API_TOKEN handshake auth (fail closed), malformed-message
tolerance, and preserved legitimate gateway operation - including one live
loopback round-trip with a real listener and a fake agent.
"""

import asyncio
import importlib
import json
import os
import socket
import subprocess
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

websockets = pytest.importorskip("websockets")
pytest.importorskip("fastmcp")

import mcp_plugins.local_agent_gateway as gw


REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
TEST_TOKEN = "gateway-test-token"


class _FakeClosed(Exception):
    pass


class FakeWebSocket:
    """Minimal stand-in for a websockets connection (no real network)."""

    def __init__(self, messages):
        self._messages = list(messages)
        self.sent = []
        self.close_calls = []

    async def recv(self):
        if not self._messages:
            raise _FakeClosed("connection closed")
        return self._messages.pop(0)

    def __aiter__(self):
        async def _gen():
            while self._messages:
                yield self._messages.pop(0)

        return _gen()

    async def send(self, payload):
        self.sent.append(payload)

    async def close(self, code=1000, reason=""):
        self.close_calls.append((code, reason))


def _run(coro):
    return asyncio.run(coro)


class TestStartupBehavior:
    def test_import_does_not_start_server(self):
        code = (
            "import sys; sys.path.insert(0, '.');"
            "import threading;"
            "import mcp_plugins.local_agent_gateway as g;"
            "assert g._bridge_loop is None, g._bridge_loop;"
            "assert g._bridge_thread is None, g._bridge_thread;"
            "names = [t.name for t in threading.enumerate()];"
            "assert 'fox-agent-gateway' not in names, names;"
            "print('IMPORT_CLEAN')"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "IMPORT_CLEAN" in result.stdout

    def test_loopback_default(self, monkeypatch):
        monkeypatch.delenv("AGENT_GATEWAY_HOST", raising=False)
        reloaded = importlib.reload(gw)
        assert reloaded.AGENT_HOST == "127.0.0.1"

    def test_explicit_host_override_still_honored(self, monkeypatch):
        monkeypatch.setenv("AGENT_GATEWAY_HOST", "0.0.0.0")
        reloaded = importlib.reload(gw)
        assert reloaded.AGENT_HOST == "0.0.0.0"


class TestHandshakeAuth:
    def test_missing_server_token_fails_closed(self, monkeypatch):
        monkeypatch.delenv("FOX_API_TOKEN", raising=False)
        ws = FakeWebSocket([json.dumps({"token": "anything"})])
        _run(gw._handle_agent(ws))
        assert ws.close_calls and ws.close_calls[0][0] == 4401
        assert gw._agent_conn is None

    def test_wrong_token_rejected(self, monkeypatch):
        monkeypatch.setenv("FOX_API_TOKEN", TEST_TOKEN)
        ws = FakeWebSocket([json.dumps({"token": "wrong-token"})])
        _run(gw._handle_agent(ws))
        assert ws.close_calls and ws.close_calls[0][0] == 4401
        assert gw._agent_conn is None
        # the presented secret must never be echoed back
        assert all("wrong-token" not in (reason or "") for _, reason in ws.close_calls)

    def test_missing_token_in_handshake_rejected(self, monkeypatch):
        monkeypatch.setenv("FOX_API_TOKEN", TEST_TOKEN)
        ws = FakeWebSocket([json.dumps({"id": "hello"})])
        _run(gw._handle_agent(ws))
        assert ws.close_calls and ws.close_calls[0][0] == 4401
        assert gw._agent_conn is None

    def test_malformed_handshake_rejected(self, monkeypatch):
        monkeypatch.setenv("FOX_API_TOKEN", TEST_TOKEN)
        ws = FakeWebSocket(["this is not json{{{"])
        _run(gw._handle_agent(ws))
        assert ws.close_calls and ws.close_calls[0][0] == 4400
        assert gw._agent_conn is None

    def test_non_object_handshake_rejected(self, monkeypatch):
        monkeypatch.setenv("FOX_API_TOKEN", TEST_TOKEN)
        ws = FakeWebSocket(["[1, 2, 3]"])
        _run(gw._handle_agent(ws))
        assert ws.close_calls and ws.close_calls[0][0] == 4401
        assert gw._agent_conn is None


class TestMessageValidation:
    def test_malformed_messages_do_not_kill_handler(self, monkeypatch):
        monkeypatch.setenv("FOX_API_TOKEN", TEST_TOKEN)
        ws = FakeWebSocket(
            [
                json.dumps({"token": TEST_TOKEN}),
                "not json at all",
                "[1, 2, 3]",
                "42",
                '"just a string"',
                json.dumps({"id": ["unhashable"]}),
                json.dumps({"id": {"nested": "dict"}}),
                json.dumps({"no_id": 1}),
                json.dumps({"id": "unknown-id", "ok": True}),
            ]
        )
        # must not raise: every malformed message is skipped cleanly
        _run(gw._handle_agent(ws))
        assert ws.close_calls == []
        assert gw._agent_conn is None


class TestPreservedBehavior:
    def test_agent_status_reports_connection_state(self, monkeypatch):
        monkeypatch.setattr(gw, "_agent_conn", None)
        assert "No agent connected" in gw.agent_status()
        monkeypatch.setattr(gw, "_agent_conn", object())
        assert "Agent connected" in gw.agent_status()

    def test_screenshot_without_agent_preserved(self, monkeypatch):
        monkeypatch.setattr(gw, "_agent_conn", None)
        assert "No local agent connected" in gw.desktop_screenshot()

    def test_send_without_bridge_reports_not_started(self, monkeypatch):
        monkeypatch.setattr(gw, "_agent_conn", object())
        monkeypatch.setattr(gw, "_bridge_loop", None)
        reply = gw._send_to_agent("screenshot", {})
        assert reply == {"ok": False, "error": "Bridge not started yet....."}


def _free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class TestLiveLoopbackRoundTrip:
    """End-to-end over real loopback: listener, auth, command, reply."""

    def test_authenticated_agent_command_round_trip(self, monkeypatch):
        monkeypatch.setenv("FOX_API_TOKEN", TEST_TOKEN)
        port = _free_port()
        monkeypatch.setattr(gw, "AGENT_HOST", "127.0.0.1")
        monkeypatch.setattr(gw, "AGENT_PORT", port)
        gw.start_gateway()

        stop = threading.Event()

        async def fake_agent():
            conn = None
            deadline = time.time() + 10
            while conn is None and time.time() < deadline and not stop.is_set():
                try:
                    conn = await websockets.connect(f"ws://127.0.0.1:{port}")
                except OSError:
                    await asyncio.sleep(0.1)
            if conn is None:
                return
            async with conn:
                await conn.send(json.dumps({"token": TEST_TOKEN, "id": "hello"}))
                try:
                    while not stop.is_set():
                        try:
                            raw = await asyncio.wait_for(conn.recv(), timeout=0.5)
                        except asyncio.TimeoutError:
                            continue
                        msg = json.loads(raw)
                        await conn.send(
                            json.dumps({"id": msg["id"], "ok": True, "result": "fake-shot"})
                        )
                except Exception:
                    pass

        agent_thread = threading.Thread(target=lambda: asyncio.run(fake_agent()), daemon=True)
        agent_thread.start()
        try:
            deadline = time.time() + 10
            while gw._agent_conn is None and time.time() < deadline:
                time.sleep(0.05)
            assert gw._agent_conn is not None, "agent never authenticated"

            reply = gw._send_to_agent("screenshot", {"app_name": ""})
            assert reply.get("ok") is True
            assert reply.get("result") == "fake-shot"
        finally:
            stop.set()
            agent_thread.join(timeout=10)
            deadline = time.time() + 10
            while gw._agent_conn is not None and time.time() < deadline:
                time.sleep(0.05)
            assert gw._agent_conn is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
