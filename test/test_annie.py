# test fot annie!

import json

from agent.annie.annie import Annie, AnnieResult
from agent.julie.julie import JulieResult


class FakeAnnieBackend:
    def __init__(self, response):
        self.response = response
        self.messages = []

    def generate(self, messages):
        self.messages.append(messages)
        return self.response


def make_julie_result():
    return JulieResult(
        user_request="Organize my Downloads folder",
        context=None,
        expanded_task="Inspect and organize the Downloads folder.",
        plan=[
            "Identify all files in Downloads",
            "Categorize the files",
            "Create appropriate folders",
            "Move files into the folders",
        ],
        uncertainty=[
            "The user has not specified a preferred folder structure."
        ],
        raw_response="fake julie response",
    )


def valid_response():
    return json.dumps({
        "interpretation": (
            "The user wants the Downloads folder inspected and "
            "organized into sensible categories."
        ),
        "requirements": [
            "Inspect the current Downloads contents",
            "Categorize files",
            "Organize files into appropriate folders",
        ],
        "constraints": [
            "Do not invent a folder structure without evidence",
            "Inspect before modifying files",
        ],
        "technical_handoff": (
            "Selina should inspect the Downloads folder first, "
            "then determine a safe organization strategy before "
            "making modifications."
        ),
        "clarification_needed": [
            "Preferred folder structure is not specified."
        ],
    })


def test_annie_creates_structured_handoff():
    backend = FakeAnnieBackend(valid_response())
    annie = Annie(backend)

    result = annie.structure(make_julie_result())

    assert isinstance(result, AnnieResult)

    assert result.user_request == "Organize my Downloads folder"
    assert result.interpretation
    assert result.requirements
    assert result.constraints
    assert result.technical_handoff
    assert result.clarification_needed


def test_annie_preserves_uncertainty():
    backend = FakeAnnieBackend(valid_response())
    annie = Annie(backend)

    result = annie.structure(make_julie_result())

    assert any(
        "folder structure" in item.lower()
        for item in result.clarification_needed
    )


def test_annie_does_not_execute_tools():
    backend = FakeAnnieBackend(valid_response())
    annie = Annie(backend)

    result = annie.structure(make_julie_result())

    assert isinstance(result, AnnieResult)

    # Annie should describe what Selina needs to do,
    # not execute the operation herself.
    assert "Selina" in result.technical_handoff


def test_annie_refines_from_selina_feedback():
    backend = FakeAnnieBackend(valid_response())
    annie = Annie(backend)

    original = annie.structure(make_julie_result())

    refined_response = json.dumps({
        "interpretation": original.interpretation,
        "requirements": original.requirements,
        "constraints": [
            *original.constraints,
            "Verify file categories before moving files.",
        ],
        "technical_handoff": (
            "Selina should inspect the files, verify their categories, "
            "and only then perform file movements."
        ),
        "clarification_needed": original.clarification_needed,
    })

    backend.response = refined_response

    refined = annie.refine(
        original,
        "The categorization step needs verification before files are moved."
    )

    assert isinstance(refined, AnnieResult)

    assert any(
        "verify" in item.lower()
        for item in refined.constraints
    )

    assert "verify" in refined.technical_handoff.lower()


def test_annie_rejects_invalid_julie_result():
    backend = FakeAnnieBackend(valid_response())
    annie = Annie(backend)

    try:
        annie.structure("not a JulieResult")
        assert False
    except TypeError:
        pass


def test_annie_rejects_empty_user_request():
    backend = FakeAnnieBackend(valid_response())
    annie = Annie(backend)

    empty_result = JulieResult(
        user_request="",
        context=None,
        expanded_task="",
        plan=[],
        uncertainty=[],
        raw_response="",
    )

    try:
        annie.structure(empty_result)
        assert False
    except ValueError:
        pass