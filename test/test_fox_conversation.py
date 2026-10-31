"""Focused tests for FoxConversationManager history bounds.

MemberSession history used to grow for the life of the manager while every
turn re-sent the whole session to the model (request/token/latency/cost
growth until context-window failure). History is now capped at the most
recent FOX_HISTORY_MAX_MESSAGES entries (default 20). Ollama is always
mocked - no daemon required.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _info(*names):
    return {
        "installed": True,
        "binary": "ollama",
        "host": "http://127.0.0.1:11434",
        "running": True,
        "models": [{"name": name} for name in names],
    }


@pytest.fixture()
def manager(monkeypatch):
    from agent.fox.conversation import manager as manager_module
    from agent.fox.conversation.manager import FoxConversationManager

    info = _info("qwen3:4b")
    monkeypatch.setattr("agent.ollama.client.discover_ollama", lambda: info)
    monkeypatch.setattr(manager_module, "discover_ollama", lambda: info)
    monkeypatch.delenv("FOX_HISTORY_MAX_MESSAGES", raising=False)

    manager = FoxConversationManager(model="qwen3:4b")
    # Never touch the network: canned assistant replies.
    manager.client.chat = lambda messages, think=False: {"message": {"content": "ok"}}
    manager.switch_member("fox")
    return manager


def _drive(manager, turns):
    for i in range(turns):
        assert manager.send_message(f"question {i}") == "ok"


class TestHistoryBound:
    def test_history_stops_growing(self, manager):
        _drive(manager, 50)
        history = manager.get_session("fox").history
        assert len(history) == 20

    def test_most_recent_messages_are_kept(self, manager):
        _drive(manager, 50)
        contents = [m.content for m in manager.get_session("fox").history]
        assert contents[-1] == "ok"
        assert "question 49" in contents
        assert "question 0" not in contents

    def test_short_conversations_untouched(self, manager):
        _drive(manager, 3)
        history = manager.get_session("fox").history
        assert [m.content for m in history] == [
            "question 0", "ok",
            "question 1", "ok",
            "question 2", "ok",
        ]
        assert [m.role for m in history] == [
            "user", "assistant",
            "user", "assistant",
            "user", "assistant",
        ]

    def test_bound_is_per_member_session(self, manager):
        _drive(manager, 50)
        manager.switch_member("julie")
        _drive(manager, 2)
        assert len(manager.get_session("fox").history) == 20
        assert len(manager.get_session("julie").history) == 4

    def test_clear_history_still_works(self, manager):
        _drive(manager, 50)
        manager.clear_history("fox")
        assert manager.get_session("fox").history == []


class TestBoundConfiguration:
    def test_env_override_is_honoured(self, manager, monkeypatch):
        monkeypatch.setenv("FOX_HISTORY_MAX_MESSAGES", "4")
        _drive(manager, 50)
        assert len(manager.get_session("fox").history) == 4

    def test_invalid_env_falls_back_to_default(self, manager, monkeypatch, capsys):
        from agent.fox.conversation import manager as manager_module

        monkeypatch.setenv("FOX_HISTORY_MAX_MESSAGES", "lots")
        _drive(manager, 50)
        assert len(manager.get_session("fox").history) == manager_module.HISTORY_MAX_MESSAGES_DEFAULT

    def test_floor_keeps_a_full_exchange(self, monkeypatch):
        from agent.fox.conversation import manager as manager_module

        monkeypatch.setenv("FOX_HISTORY_MAX_MESSAGES", "0")
        assert manager_module.history_max_messages() == 2


class TestBoundedPayload:
    def test_chat_receives_system_prompt_plus_bounded_history(self, manager):
        seen = []
        manager.client.chat = lambda messages, think=False: (
            seen.append(messages) or {"message": {"content": "ok"}}
        )
        _drive(manager, 50)

        last = seen[-1]
        assert last[0]["role"] == "system"
        # system prompt + at most the retained session messages
        assert len(last) <= 1 + 20
        # the payload carries recent context, not the ancient start
        assert any("question 49" in m["content"] for m in last[1:])
        assert not any("question 0" in m["content"] for m in last[1:])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
