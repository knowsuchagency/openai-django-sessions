"""Django models for agent session storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    pass

# Cache for dynamically created models to avoid recreating them
_model_cache: dict[tuple[str, str], tuple[type, type]] = {}


def get_session_model(table_name: str = "agent_sessions") -> type[models.Model]:
    """Factory to create AgentSession model with custom table name.

    Args:
        table_name: Database table name for sessions.

    Returns:
        A Django Model class for storing session metadata.
    """
    # Check cache first
    cache_key = (table_name, "")
    if cache_key in _model_cache:
        return _model_cache[cache_key][0]

    class AgentSession(models.Model):
        """Tracks conversation sessions with timestamps."""

        session_id = models.CharField(max_length=255, unique=True, db_index=True)
        created_at = models.DateTimeField(auto_now_add=True)
        updated_at = models.DateTimeField(auto_now=True)

        class Meta:
            db_table = table_name
            app_label = "openai_django_sessions"

        def __str__(self) -> str:
            return f"Session({self.session_id})"

    return AgentSession


def get_message_model(
    session_model: type[models.Model],
    table_name: str = "agent_messages",
) -> type[models.Model]:
    """Factory to create AgentMessage model with custom table name.

    Args:
        session_model: The session model class to create foreign key to.
        table_name: Database table name for messages.

    Returns:
        A Django Model class for storing conversation messages.
    """
    # Check cache
    session_table = session_model._meta.db_table
    cache_key = (session_table, table_name)
    if cache_key in _model_cache:
        return _model_cache[cache_key][1]

    class AgentMessage(models.Model):
        """Stores individual conversation items as JSON."""

        session = models.ForeignKey(
            session_model,
            on_delete=models.CASCADE,
            related_name="messages",
        )
        data = models.JSONField()
        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            db_table = table_name
            app_label = "openai_django_sessions"
            ordering = ["created_at", "id"]

        def __str__(self) -> str:
            return f"Message({self.id})"

    # Cache the pair
    _model_cache[cache_key] = (session_model, AgentMessage)

    return AgentMessage


def get_models(
    sessions_table: str = "agent_sessions",
    messages_table: str = "agent_messages",
) -> tuple[type[models.Model], type[models.Model]]:
    """Get both session and message models with custom table names.

    Args:
        sessions_table: Database table name for sessions.
        messages_table: Database table name for messages.

    Returns:
        Tuple of (SessionModel, MessageModel).
    """
    cache_key = (sessions_table, messages_table)
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    session_model = get_session_model(sessions_table)
    message_model = get_message_model(session_model, messages_table)
    _model_cache[cache_key] = (session_model, message_model)
    return session_model, message_model


# Lazy-loaded default models (created on first access)
_default_session_model: type | None = None
_default_message_model: type | None = None


def _get_default_session_model():
    """Get the default AgentSession model, creating it if needed."""
    global _default_session_model
    if _default_session_model is None:
        _default_session_model = get_session_model()
    return _default_session_model


def _get_default_message_model():
    """Get the default AgentMessage model, creating it if needed."""
    global _default_message_model
    if _default_message_model is None:
        _default_message_model = get_message_model(_get_default_session_model())
    return _default_message_model


# Module-level __getattr__ for lazy attribute access
def __getattr__(name: str):
    if name == "AgentSession":
        return _get_default_session_model()
    if name == "AgentMessage":
        return _get_default_message_model()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
