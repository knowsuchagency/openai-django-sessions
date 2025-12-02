"""Django ORM-based session backend for OpenAI Agents SDK."""

from .session import DjangoSession
from .models import get_session_model, get_message_model

# Lazy imports for AgentSession and AgentMessage
def __getattr__(name: str):
    if name == "AgentSession":
        from .models import AgentSession
        return AgentSession
    if name == "AgentMessage":
        from .models import AgentMessage
        return AgentMessage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DjangoSession",
    "AgentSession",
    "AgentMessage",
    "get_session_model",
    "get_message_model",
]
