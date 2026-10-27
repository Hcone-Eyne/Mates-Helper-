"""Regression tests: Fox Club actions beyond list/organise/find, and the
/talk member personas.

Bug: "[Fox]: Could not determine an action from Annie's requirements."
- Selina only knew 3 actions, so delete/move/copy/etc. never resolved.
- Annie phrases requirements abstractly, so the verb was often lost.
- `/talk annie` was matched against the whole line and fell through to the
  task pipeline, so the members never actually chatted.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.annie.annie import Annie, AnnieResult
from agent.selina.selina import Selina, _resolve_action
from agent.fox.security import FoxSecurityBoundary


def _annie(requirements, *, action="", arguments=None, user_request="x",
           interpretation="", handoff="do it"):
    return AnnieResult(
        user_request=user_request,
        interpretation=interpretation,
        requirements=requirements,
        constraints=[],
        technical_handoff=handoff,
        clarification_needed=[],
        raw_response="{}",
        action=action,
        arguments=arguments or {},
    )


@pytest.mark.parametrize("text,expected", [
    ("delete notes.txt", "delete_file"),
    ("remove the old report", "delete_file"),
    ("restore notes.txt from trash", "restore_file"),
    ("move a.txt into Archive", "move_file"),
    ("copy a.txt to Backup", "copy_file"),
    ("rename a.txt to b.txt", "rename_file"),
    ("create a folder called Work", "create_folder"),
    ("delete the file in that directory", "delete_file"),
])
def test_new_actions_resolve(text, expected):
    assert _resolve_action([text]) == expected


def test_explicit_annie_action_wins():
    executor = MagicMock(return_value=None)
    selina = Selina(executor)
    result = selina.execute_from_annie(
        _annie(["Identify the target"], action="delete_file",
               arguments={"path": "notes.txt"})
    )
    assert result.success
    executor.execute.assert_called_once()
    kwargs = executor.execute.call_args.kwargs
    assert kwargs["action"] == "delete_file"
    assert kwargs["arguments"]["path"] == "notes.txt"
    # Annie's context still travels along, but never overrides arguments
    assert kwargs["arguments"]["user_request"] == "x"


def test_unknown_explicit_action_falls_back_to_keywords():
    executor = MagicMock()
    selina = Selina(executor)
    result = selina.execute_from_annie(
        _annie(["list everything"], action="format_disk")
    )
    assert result.action == "list_directory"


def test_selina_does_not_guess_from_free_text():
    """Abstract requirements + no explicit action must fail loudly."""
    executor = MagicMock()
    selina = Selina(executor)
    result = selina.execute_from_annie(
        _annie(["Identify the target files", "Confirm with user"],
               user_request="please move report.pdf to Archive")
    )
    assert result.success is False
    assert "Could not determine an action" in result.error
    executor.execute.assert_not_called()


@pytest.mark.parametrize("text", [
    "Delete everything",
    "remove all files",
    "move every file to Archive",
])
def test_bulk_destructive_wording_never_resolves(text):
    assert _resolve_action([text]) == ""


def test_annie_parses_optional_action_and_arguments():
    data = Annie._parse_response(
        '{"interpretation": "i", "requirements": [], "constraints": [],'
        ' "technical_handoff": "t", "clarification_needed": [],'
        ' "action": "delete_file", "arguments": {"path": "a.txt"}}'
    )
    assert data["action"] == "delete_file"
    assert data["arguments"] == {"path": "a.txt"}


def test_annie_tolerates_missing_or_bad_optional_fields():
    data = Annie._parse_response(
        '{"interpretation": "i", "requirements": [], "constraints": [],'
        ' "technical_handoff": "t", "clarification_needed": [],'
        ' "action": 5, "arguments": "nope"}'
    )
    assert data["action"] == ""
    assert data["arguments"] == {}


def test_boundary_accepts_find_files(tmp_path):
    boundary = FoxSecurityBoundary(tmp_path)
    assert boundary.validate_action("find_files") == "search_files"


def test_each_member_has_distinct_persona():
    from agent.fox.conversation.manager import MEMBER_PERSONAS

    assert set(MEMBER_PERSONAS) == {"julie", "annie", "selina", "gwen", "fox"}
    assert "planner" in MEMBER_PERSONAS["julie"]
    assert "manager" in MEMBER_PERSONAS["annie"]
    assert "action player" in MEMBER_PERSONAS["selina"]
    assert "reviewer" in MEMBER_PERSONAS["gwen"]
    # no two members share the same prompt
    assert len(set(MEMBER_PERSONAS.values())) == 5


def test_talk_uses_member_persona(monkeypatch):
    from agent.fox.conversation import manager as manager_module
    from agent.fox.conversation.manager import FoxConversationManager, MEMBER_PERSONAS

    info = {"installed": True, "binary": "ollama",
            "host": "http://127.0.0.1:11434", "running": True,
            "models": [{"name": "qwen3:4b"}]}
    monkeypatch.setattr("agent.ollama.client.discover_ollama", lambda: info)
    monkeypatch.setattr(manager_module, "discover_ollama", lambda: info)

    mgr = FoxConversationManager(model="qwen3:4b")
    seen = {}

    def fake_chat(messages, think=False):
        seen["system"] = messages[0]["content"]
        return {"message": {"content": "hi"}}

    mgr.client.chat = fake_chat
    mgr.switch_member("gwen")
    assert mgr.send_message("who are you?") == "hi"
    assert seen["system"] == MEMBER_PERSONAS["gwen"]


def test_parsers_strip_qwen3_think_block():
    from agent.julie.julie import Julie
    from agent.gwen.gwen import Gwen

    julie_raw = (
        'thinking...\n</think>\n'
        '{"expanded_task": "list files", "plan": ["step 1"], "uncertainty": []}'
    )
    assert Julie._parse_result(julie_raw)["expanded_task"] == "list files"

    annie_raw = (
        'thinking...\n</think>\n'
        '{"interpretation": "i", "requirements": ["list files"],'
        ' "constraints": [], "technical_handoff": "t",'
        ' "clarification_needed": [], "action": "list_directory"}'
    )
    assert Annie._parse_response(annie_raw)["action"] == "list_directory"

    gwen_raw = (
        'thinking...\n</think>\n'
        '{"approved": true, "issues": [], "safety_concerns": [], "recommendations": []}'
    )
    assert Gwen._parse_structured_response(gwen_raw)["approved"] is True

