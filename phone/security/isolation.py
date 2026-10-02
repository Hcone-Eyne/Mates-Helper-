# this program the isolation of sensitive information, so ai agent won't get all access, only restricted access

# importing the nessary modules
import re
import sys
from pathlib import Path


# class fot this to prevent error
class PhoneIsolationError(PermissionError):
    ...


# The only identities allowed to drive the Phone Hub.
#
# This is deliberately an allowlist. The boundary used to deny a fixed list of
# agent names and trust everything else, so any caller could invent a source
# label that had never been audited. Anything not enumerated here is refused.
_TRUSTED_SOURCES = frozenset({
    "phone_cli",
    "system",
    "user",
    "kdeconnect",
    "",  # historical default: callers that never declared a source
})

# Package directories in this repository that belong to the agent side.
_AGENT_PACKAGE_DIRS = frozenset({
    "agent",
    "brain",
    "mcp_plugins",
    "Agent_plugins",
    "proxy",
})

# Frames belonging to this package are skipped - they are the boundary itself.
_PHONE_PACKAGE = "phone"

_MAX_CALLER_DEPTH = 64


def _canonical(source: str) -> str:
    """Normalise a source label into a comparable identity."""
    return re.sub(r"[^a-z0-9]+", "_", (source or "").strip().lower()).strip("_")


def _agent_side_caller() -> str | None:
    """Return the agent-side module a phone call originates from, if any.

    The declared ``source`` is only a label the caller writes down, so it can
    be lied about. The call stack cannot: this walks outward from the check
    and reports the first frame that lives inside an agent-side package of
    this repository.
    """
    try:
        repo_root = Path(__file__).resolve().parents[2]
    except IndexError:
        return None

    frame = sys._getframe(1)
    depth = 0
    while frame is not None and depth < _MAX_CALLER_DEPTH:
        depth += 1
        filename = frame.f_code.co_filename
        if filename and not filename.startswith("<"):
            try:
                relative = Path(filename).resolve().relative_to(repo_root)
            except (OSError, ValueError):
                pass
            else:
                parts = relative.parts
                if parts and parts[0] != _PHONE_PACKAGE and parts[0] in _AGENT_PACKAGE_DIRS:
                    return str(relative)
        frame = frame.f_back
    return None


def assert_phone_boundary(source: str):
    """Reject phone access from agent-side callers.

    Two independent checks run on every call:

    1. The declared ``source`` must be one of the allowlisted identities -
       unknown or untrusted labels are refused, not merely known agent names.
    2. The actual call stack must not originate inside an agent-side package,
       so a caller cannot simply label itself ``phone_cli``.
    """
    identity = _canonical(source)
    if identity not in _TRUSTED_SOURCES:
        raise PhoneIsolationError(
            "Phone data is isolated from agent! "
            f"Source {source!r} is not an allowlisted Phone Hub caller."
        )

    caller = _agent_side_caller()
    if caller is not None:
        raise PhoneIsolationError(
            "Phone data is isolated from agent! "
            f"Call originates in agent-side module {caller}."
        )
