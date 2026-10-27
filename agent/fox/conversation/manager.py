# Fox Conversation Manager
# Direct conversational interface to Fox Club members.
# Each member maintains their own conversation history.

from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path
import os

from agent.ollama.client import OllamaClient
from agent.ollama.discovery import discover_ollama
from agent.julie.julie import Julie, JulieResult, OllamaReasoningBackend
from agent.annie.annie import Annie, AnnieResult, OllamaAnnieBackend
from agent.selina.selina import Selina, SelinaResult, ActionExecutor
from agent.gwen.gwen import Gwen, GwenResult, OllamaCriticBackend
from agent.fox.fox import Fox
from agent.fox.runtime.executor import FileActionExecutor
from agent.fox.runtime.runtime import build_runtime, _UnavailableExecutor
from agent.fox.security import FoxSecurityBoundary
from agent.fox.Fox_Space import ensure_fox_space


@dataclass
class ConversationMessage:
    """A single message in a conversation."""
    role: str  # "user" or "assistant"
    content: str


# Default cap on retained messages per member session (user + assistant
# counted together). Bounds every turn's payload to recent context instead
# of the whole session. Overridable via FOX_HISTORY_MAX_MESSAGES, following
# the project's env-configuration convention (OLLAMA_MODEL, FOX_API_TOKEN,
# FOX_TASK_TIMEOUT_SECONDS, ...).
HISTORY_MAX_MESSAGES_DEFAULT = 20


def history_max_messages() -> int:
    """Resolve the session history bound. Invalid values fall back to the
    default; the floor of 2 keeps at least one full exchange."""
    try:
        return max(2, int(os.environ.get("FOX_HISTORY_MAX_MESSAGES", HISTORY_MAX_MESSAGES_DEFAULT)))
    except (TypeError, ValueError):
        return HISTORY_MAX_MESSAGES_DEFAULT


# ---------------------------------------------------------------------------
# Conversation personas
# ---------------------------------------------------------------------------
# These are used ONLY by /talk <member>. The task pipeline (Julie -> Annie ->
# Selina -> Gwen) keeps its own strict JSON prompts inside each agent file.
# Every persona shares the same club facts so the members agree with each
# other, then adds that member's own job, voice and limits.

_CLUB_FACTS = """
About Fox Club (shared knowledge - every member knows this):
- Fox Club lives inside Mates Helper, a CLI app for schedule, finance,
  phone (KDE Connect) and a private file space called Fox Space.
- The task pipeline is: Julie (plans) -> Annie (manager, writes the handoff)
  -> Selina (does the work) -> Gwen (reviews it). If Gwen rejects, Annie
  refines and Selina tries again. A Python orchestrator (the Brain) runs it.
- Selina can only: list, search, organise, create folders, move, copy,
  rename, delete (to trash) and restore files inside Fox Space.
- Nobody in the club can read the user's phone. Phone is user-only.
- The goal of the club is accurate answers with no hallucination. If you do
  not know something, say so plainly instead of guessing.
- Right now you are in chat mode: you are talking, not executing. Nothing
  you say here touches any file. To run a task the user types /back and
  writes the task in task mode.
""".strip()

MEMBER_PERSONAS = {
    "julie": f"""
You are Julie, the planner of Fox Club.

Your job: take what the user says and turn it into a clear goal and a short,
ordered list of steps. You are the first member to see every task.

How you talk:
- Calm, curious and organised. You think out loud in numbered steps.
- When a request is vague you ask one focused question instead of guessing.
- You point out what is still unknown ("I don't know which folder you mean").
- You never claim a step is done - you only plan.

Introduce yourself as Julie, the planner, if asked who you are.

{_CLUB_FACTS}
""".strip(),

    "annie": f"""
You are Annie, the manager of Fox Club.

Your job: take Julie's plan and turn it into an exact assignment for Selina
- which action, which file, which folder - and tell Gwen what to check.
You decide who does what.

How you talk:
- Confident, direct and a little bossy, like a team lead running stand-up.
- You separate "what is required" from "what is not allowed".
- You refuse to invent file names, paths or user preferences; if something
  is missing you say exactly what you still need from the user.
- You speak about Selina and Gwen as your team ("I'll hand this to Selina").

Introduce yourself as Annie, the manager, if asked who you are.

{_CLUB_FACTS}
""".strip(),

    "selina": f"""
You are Selina, the action player of Fox Club.

Your job: you are the one who actually does the work Annie assigns, using
the Fox Space file tools. Gwen checks your work after you finish.

How you talk:
- Short, practical and hands-on. You like getting things done.
- You explain exactly which tool you would use and with what arguments,
  e.g. "That's a move_file from notes.txt to Archive/".
- You are honest about your limits: you only work inside Fox Space and
  you cannot touch the phone, the internet or system files.
- In chat mode you do not run anything - you explain how you would.

Introduce yourself as Selina, the action player, if asked who you are.

{_CLUB_FACTS}
""".strip(),

    "gwen": f"""
You are Gwen, the reviewer and security check of Fox Club.

Your job: after Selina acts, you compare her result against what Annie
assigned. If anything is wrong, unsafe or made up, you report it to the
Brain so it can be fixed.

How you talk:
- Sharp, skeptical and fair. You look for what could go wrong.
- You give verdicts clearly: what is fine, what is wrong, and why.
- You flag anything destructive (deleting, overwriting) and anything that
  sounds like a guess rather than a fact.
- You give credit when work is correct - you are strict, not rude.

Introduce yourself as Gwen, the reviewer, if asked who you are.

{_CLUB_FACTS}
""".strip(),

    "fox": f"""
You are Fox, the front desk of Mates Helper and the face of Fox Club.

Your job: chat with the user, answer general questions and point them to
the right place - Schedule, Finance, Phone, Files, or a Fox Club member.

How you talk:
- Friendly, helpful and brief.
- If a question is really a file task, tell the user to type it in task
  mode so the club can handle it.
- If the user wants planning help, suggest /talk julie; reviewing ideas,
  /talk gwen; and so on.

{_CLUB_FACTS}
""".strip(),
}


@dataclass
class MemberSession:
    """Conversation session for a single Fox Club member."""
    member_name: str
    history: list[ConversationMessage] = field(default_factory=list)

    def add_user_message(self, content: str):
        self.history.append(ConversationMessage(role="user", content=content))
        self._trim()

    def add_assistant_message(self, content: str):
        self.history.append(ConversationMessage(role="assistant", content=content))
        self._trim()

    def _trim(self):
        """Keep only the most recent messages.

        Without this, every turn re-sends the entire session, so request
        size, latency, and provider cost grow for the life of the manager
        until the model context window breaks. Oldest-first is safe: the
        model always sees the latest exchanges.
        """
        limit = history_max_messages()
        if len(self.history) > limit:
            del self.history[:len(self.history) - limit]
    
    def get_messages(self) -> list[dict[str, str]]:
        """Convert history to Ollama messages format."""
        return [{"role": msg.role, "content": msg.content} for msg in self.history]
    
    def clear(self):
        self.history.clear()


class FoxConversationManager:
    """
    Manages direct conversations with Fox Club members.
    
    Each member maintains their own conversation history.
    Switching between members preserves their individual histories.
    
    Security: This conversational layer does NOT have access to:
    - FileActionExecutor
    - FoxSecurityBoundary
    - Filesystem tools
    - Phone permissions
    - Shell execution
    
    It is purely for dialogue with Fox Club members.
    """
    
    MEMBERS = {
        "julie": "Julie - Reasoning and planning agent",
        "annie": "Annie - Engineering handoff architect",
        "selina": "Selina - Task executor",
        "gwen": "Gwen - Critic and reviewer",
        "fox": "Fox - Main conversational identity",
    }
    
    def __init__(
        self,
        model: str | None = None,
        think: bool = False,
        strict: bool | None = None,
    ):
        # Discover Ollama and create shared client
        info = discover_ollama()
        self.host = info["host"].rstrip("/")
        self.think = think

        # Model resolution lives in OllamaClient: a requested-but-missing
        # model warns (or raises under strict=True / OLLAMA_STRICT_MODEL)
        # instead of being silently swapped, and self.model always reflects
        # the model that will actually run.
        self.client = OllamaClient(
            host=self.host,
            model=model,
            think=think,
            strict=strict,
        )
        self.model = self.client.model
        
        # Conversation sessions for each member
        self.sessions: dict[str, MemberSession] = {}
        for member in self.MEMBERS:
            self.sessions[member] = MemberSession(member_name=member)
        
        self.active_member: Optional[str] = None
        
        # Initialize agent backends (lazy initialization)
        self._julie: Julie | None = None
        self._annie: Annie | None = None
        self._selina: Selina | None = None
        self._gwen: Gwen | None = None
        self._fox: Fox | None = None
    
    # Lazy initialization of agent backends
    def _get_julie(self) -> Julie:
        if self._julie is None:
            backend = OllamaReasoningBackend(self.client)
            self._julie = Julie(backend)
        return self._julie
    
    def _get_annie(self) -> Annie:
        if self._annie is None:
            from agent.annie.annie import OllamaAnnieBackend
            backend = OllamaAnnieBackend(self.client)
            self._annie = Annie(backend)
        return self._annie
    
    def _get_selina(self) -> Selina:
        if self._selina is None:
            # Selina needs an executor, but in conversation mode we don't have filesystem access
            # We create a dummy executor that raises an error if used
            class ConversationExecutor:
                def execute(self, action: str, arguments: dict) -> str:
                    return "[Selina]: I cannot execute filesystem operations in conversation mode. Ask me about planning or reasoning instead."
            self._selina = Selina(ConversationExecutor())
        return self._selina
    
    def _get_gwen(self) -> Gwen:
        if self._gwen is None:
            backend = GwenResult  # placeholder
            from agent.gwen.gwen import OllamaCriticBackend
            backend = OllamaCriticBackend(self.client)
            self._gwen = Gwen(backend)
        return self._gwen
    
    def _get_fox(self) -> Fox:
        if self._fox is None:
            # Fox in conversation mode doesn't need a runtime
            self._fox = Fox(runtime=None)
        return self._fox
    
    def set_model(self, model: str | None):
        """Change the model for all members."""
        if model is not None:
            available = [m.get("name", "") for m in discover_ollama().get("models", [])]
            if model not in [m.get("name", "") for m in discover_ollama().get("models", [])]:
                raise ValueError(f"Model '{model}' not available")
        self.model = model
        self.client = OllamaClient(
            host=self.host,
            model=self.model,
            think=self.think
        )
        # Reset backends to use new client
        self._julie = None
        self._annie = None
        self._selina = None
        self._gwen = None
        self._fox = None
    
    def set_think(self, think: bool):
        """Toggle thinking mode for all members."""
        self.think = think
        self.client = OllamaClient(
            host=self.host,
            model=self.model,
            think=think
        )
        # Reset backends to use new client
        self._julie = None
        self._annie = None
        self._selina = None
        self._gwen = None
        self._fox = None
    
    def get_active_member(self) -> Optional[str]:
        return self.active_member
    
    def get_available_members(self) -> dict[str, str]:
        return self.MEMBERS.copy()
    
    def switch_member(self, member_name: str) -> bool:
        """Switch to a different member. Returns True if successful."""
        if member_name not in self.MEMBERS:
            return False
        self.active_member = member_name
        return True
    
    def get_session(self, member_name: str) -> MemberSession:
        return self.sessions[member_name]
    
    def get_active_session(self) -> Optional[MemberSession]:
        if self.active_member:
            return self.sessions[self.active_member]
        return None
    
    def send_message(self, user_input: str) -> str:
        """Send a message to the active member and get their response."""
        if not self.active_member:
            return "[Fox]: No active member. Use /talk <member> to start a conversation."
        
        if not isinstance(user_input, str):
            return "[Fox]: Input must be a string."
        
        user_input = user_input.strip()
        if not user_input:
            return ""
        
        session = self.sessions[self.active_member]
        session.add_user_message(user_input)
        
        try:
            if self.active_member == "julie":
                response = self._chat_with_julie()
            elif self.active_member == "annie":
                response = self._chat_with_annie()
            elif self.active_member == "selina":
                response = self._chat_with_selina()
            elif self.active_member == "gwen":
                response = self._chat_with_gwen()
            elif self.active_member == "fox":
                response = self._chat_with_fox()
            else:
                return f"[Fox]: Unknown member: {self.active_member}"
            
            session.add_assistant_message(response)
            return response
        except Exception as e:
            return f"[{self.active_member.capitalize()}]: Error - {e}"
    
    def _chat_as(self, member: str) -> str:
        """Chat with one member using her own persona and her own history."""
        session = self.sessions[member]

        messages = [{"role": "system", "content": MEMBER_PERSONAS[member]}]
        messages.extend(session.get_messages())

        response = self.client.chat(messages, think=self.think)

        if isinstance(response, dict):
            if "message" in response and isinstance(response["message"], dict):
                return response["message"]["content"]
            if "content" in response:
                return response["content"]
        return str(response)

    def _chat_with_julie(self) -> str:
        return self._chat_as("julie")

    def _chat_with_annie(self) -> str:
        return self._chat_as("annie")

    def _chat_with_selina(self) -> str:
        return self._chat_as("selina")

    def _chat_with_gwen(self) -> str:
        return self._chat_as("gwen")

    def _chat_with_fox(self) -> str:
        return self._chat_as("fox")

    def clear_history(self, member: str | None = None):
        """Clear conversation history for a member or all members."""
        if member:
            if member in self.sessions:
                self.sessions[member].clear()
        else:
            for session in self.sessions.values():
                session.clear()
    
    def get_history(self, member: str | None = None) -> list[ConversationMessage]:
        """Get conversation history for a member or active member."""
        if member:
            return self.sessions[member].history if member in self.sessions else []
        if self.active_member:
            return self.sessions[self.active_member].history
        return []


# Backward compatibility
class ConversationManager:
    """Alias for backward compatibility."""
    def __init__(self, *args, **kwargs):
        self._manager = FoxConversationManager(*args, **kwargs)
    
    def __getattr__(self, name):
        return getattr(self._manager, name)