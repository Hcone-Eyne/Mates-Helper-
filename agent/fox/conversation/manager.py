# Fox Conversation Manager
# Direct conversational interface to Fox Club members.
# Each member maintains their own conversation history.

from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path

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


@dataclass
class MemberSession:
    """Conversation session for a single Fox Club member."""
    member_name: str
    history: list[ConversationMessage] = field(default_factory=list)
    
    def add_user_message(self, content: str):
        self.history.append(ConversationMessage(role="user", content=content))
    
    def add_assistant_message(self, content: str):
        self.history.append(ConversationMessage(role="assistant", content=content))
    
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
    ):
        # Discover Ollama and create shared client
        info = discover_ollama()
        self.host = info["host"].rstrip("/")
        self.think = think
        
        available_models = [m.get("name", "") for m in discover_ollama().get("models", [])]
        
        if model and model in available_models:
            self.model = model
        elif model and model not in available_models:
            self.model = self._select_model(discover_ollama()["models"])
        else:
            import os
            self.model = os.environ.get("OLLAMA_MODEL") or self._select_model(discover_ollama()["models"])
        
        # Shared Ollama client
        self.client = OllamaClient(
            host=self.host,
            model=self.model,
            think=think
        )
        
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
    
    def _select_model(self, models):
        if not models:
            raise RuntimeError("[Fox]: No Ollama model is found. Pull a model first.")
        names = [m.get("name", "") for m in models if m.get("name")]
        if not names:
            raise RuntimeError("[Fox]: No Ollama model is found. Pull a model first.")
        qwen_models = [n for n in names if "qwen" in n.lower()]
        return qwen_models[0] if qwen_models else names[0]
    
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
    
    def _chat_with_julie(self) -> str:
        session = self.sessions["julie"]
        
        # Conversational system prompt for Julie
        conv_prompt = """You are Julie, the reasoning agent inside Mates Helper.

Your responsibility is to:
- understand the task
- expand the task into a precise objective
- produce a concrete, ordered plan
- identify uncertainty when necessary

You do not execute tools.
You do not access the filesystem.
You do not browse the internet.
You do not perform external actions.

For conversational mode: You may respond naturally without strict JSON formatting.
Engage in dialogue, answer questions, and explain your reasoning naturally.
You do not need to output JSON unless explicitly asked for structured output."""
        
        messages = [{"role": "system", "content": conv_prompt}]
        messages.extend(session.get_messages())
        
        response = self.client.chat(messages, think=self.think)
        
        if isinstance(response, dict):
            if "message" in response and isinstance(response["message"], dict):
                return response["message"]["content"]
            if "content" in response:
                return response["content"]
        return str(response)
    
    def _chat_with_annie(self) -> str:
        session = self.sessions["annie"]
        
        # Annie's conversational prompt (replaces the JSON-formatting system prompt)
        conv_prompt = """You are Annie, a semantic software engineer in Fox Club.

Your job is to receive Julie's reasoning and turn it into a
clear engineering handoff for Selina.

Your responsibilities:
1. Understand the user's actual intent.
2. Structure the task clearly.
3. Separate requirements from constraints.
4. Identify missing information.
5. Explain what Selina needs to accomplish technically.
6. Preserve uncertainty instead of inventing user preferences.
7. Do not invent facts.
8. Do not execute commands.
9. Do not access files, directories, browsers, APIs, or external tools.
10. Do not generate arbitrary shell commands as the primary output.

You and Selina are peer engineers with different perspectives.

Annie owns:
- semantics
- requirements
- intent
- task structure
- ambiguity

Selina owns:
- technical interpretation
- implementation
- commands
- tools
- filesystem operations
- execution

Your handoff must therefore describe WHAT needs to happen,
not pretend to already know HOW every technical operation will happen.

If Selina later reports that your interpretation is technically
ambiguous or incorrect, you should be able to refine your interpretation.

IMPORTANT:
- Missing user preferences are uncertainties, not errors.
- Do not invent folder structures, filenames, paths, or commands
  unless they are explicitly provided.
- A future step in Julie's plan is not considered completed merely
  because it exists in the plan.

For conversational mode: You may respond naturally in conversation.
You can discuss engineering concepts, clarify requirements, and explain technical concepts.
You don't need to output JSON unless asked for a structured handoff."""
        
        messages = [{"role": "system", "content": conv_prompt}]
        messages.extend(session.get_messages())
        
        response = self.client.chat(messages, think=self.think)
        
        if isinstance(response, dict):
            if "message" in response and isinstance(response["message"], dict):
                return response["message"]["content"]
            if "content" in response:
                return response["content"]
        return str(response)
    
    def _chat_with_selina(self) -> str:
        selina = self._get_selina()
        session = self.sessions["selina"]
        
        # Selina's conversational prompt
        conv_prompt = """You are Selina, the technical executor in Fox Club.

In conversation mode: You can discuss technical implementation, explain how things work, 
and help plan technical tasks. You don't have filesystem access in conversation mode,
but you can discuss technical architecture, algorithms, and implementation approaches.

Be direct, technical, and practical."""
        
        messages = [{"role": "system", "content": conv_prompt}]
        messages.extend(session.get_messages())
        
        response = self.client.chat(messages, think=self.think)
        
        if isinstance(response, dict):
            if "message" in response and isinstance(response["message"], dict):
                return response["message"]["content"]
            if "content" in response:
                return response["content"]
        return str(response)
    
    def _chat_with_gwen(self) -> str:
        session = self.sessions["gwen"]
        
        # Gwen's conversational prompt (replaces the structured review prompt)
        conv_prompt = """You are Gwen, the critic agent inside Mates Helper.

Your job is to critically review both Julie's reasoning and Selina's execution.

You will receive:
- The original user request
- Julie's expanded task, plan, and uncertainty
- Selina's interpretation, action, success status, result, and error

Check for:
- logical mistakes in Julie's plan
- missing assumptions
- incomplete reasoning
- contradictions between Julie's plan and Selina's execution
- unsafe actions
- invalid conclusions
- unnecessary or incorrect steps
- whether Selina's execution matched Julie's plan
- whether Selina's result is consistent with the expected outcome

You must decide whether the reasoning and execution are acceptable.

For conversational mode: You can discuss reasoning, point out potential issues,
and provide constructive feedback. Be thoughtful and constructive in your critiques.
You don't need to output the APPROVED/CRITIQUE format unless explicitly asked."""
        
        messages = [{"role": "system", "content": conv_prompt}]
        messages.extend(session.get_messages())
        
        response = self.client.chat(messages, think=self.think)
        
        if isinstance(response, dict):
            if "message" in response and isinstance(response["message"], dict):
                return response["message"]["content"]
            if "content" in response:
                return response["content"]
        return str(response)
    
    def _chat_with_fox(self) -> str:
        # Fox is the main conversational identity - direct chat
        session = self.sessions["fox"]
        
        fox_prompt = """You are Fox, the main conversational identity of the Fox Club.

You are helpful, direct, and honest. You can discuss any topic, answer questions,
and engage in natural conversation. You have access to the Fox Club members for
specialized tasks, but in this conversation you are the primary interface.

Be conversational, helpful, and direct."""
        
        messages = [{"role": "system", "content": fox_prompt}]
        messages.extend(self.sessions["fox"].get_messages())
        
        response = self.client.chat(messages, think=self.think)
        
        if isinstance(response, dict):
            if "message" in response and isinstance(response["message"], dict):
                return response["message"]["content"]
            if "content" in response:
                return response["content"]
        return str(response)
    
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