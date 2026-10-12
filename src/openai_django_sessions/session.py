"""Django ORM-powered session backend for OpenAI Agents SDK."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from django.db import connection, transaction

from agents.memory.session import SessionABC

if TYPE_CHECKING:
    from agents.items import TResponseInputItem


class DjangoSession(SessionABC):
    """Django ORM-powered session backend for OpenAI Agents SDK.

    This session implementation stores conversation history in a Django-managed
    database, supporting any database backend that Django supports (PostgreSQL,
    MySQL, SQLite, etc.).

    Example:
        ```python
        from agents import Agent, Runner
        from openai_django_sessions import DjangoSession

        session = DjangoSession("user-123", create_tables=True)
        agent = Agent("Assistant")
        result = await Runner.run(agent, "Hello!", session=session)
        ```
    """

    def __init__(
        self,
        session_id: str,
        *,
        sessions_table: str = "agent_sessions",
        messages_table: str = "agent_messages",
        create_tables: bool = False,
        skip_duplicate_items: bool = False,
    ) -> None:
        """Initialize a Django session.

        Args:
            session_id: Unique identifier for this conversation session.
            sessions_table: Database table name for session metadata.
            messages_table: Database table name for conversation messages.
            create_tables: If True, create tables if they don't exist.
                          Only use in development/testing.
            skip_duplicate_items: If True, ``add_items`` skips any item identical
                          to one this instance already added. Useful when several
                          agents run in turn on the same session with the same
                          user input, which would otherwise store that input
                          once per run.
        """
        self.session_id = session_id
        self._skip_duplicate_items = skip_duplicate_items
        self._added_item_keys: set[str] = set()
        self._sessions_table = sessions_table
        self._messages_table = messages_table

        # Create model classes with custom table names
        from .models import get_models

        self._session_model, self._message_model = get_models(
            sessions_table, messages_table
        )

        if create_tables:
            self._ensure_tables()

    @classmethod
    def from_settings(
        cls,
        session_id: str,
        *,
        sessions_table: str = "agent_sessions",
        messages_table: str = "agent_messages",
        create_tables: bool = False,
        skip_duplicate_items: bool = False,
    ) -> DjangoSession:
        """Create a session using Django's configured database settings.

        This is a semantic alias for the constructor, as Django automatically
        uses the configured database settings.

        Args:
            session_id: Unique identifier for this conversation session.
            sessions_table: Database table name for session metadata.
            messages_table: Database table name for conversation messages.
            create_tables: If True, create tables if they don't exist.
            skip_duplicate_items: If True, skip items this instance already added.

        Returns:
            A new DjangoSession instance.
        """
        return cls(
            session_id,
            sessions_table=sessions_table,
            messages_table=messages_table,
            create_tables=create_tables,
            skip_duplicate_items=skip_duplicate_items,
        )

    @staticmethod
    def _item_key(item: TResponseInputItem) -> str:
        """Return a stable content hash for a conversation item."""
        payload = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _ensure_tables(self) -> None:
        """Create tables if they don't exist (sync operation at init time).

        Note: This should only be called from a sync context (e.g., during
        Django startup, in a management command, or in a sync test setup).
        For async contexts, create tables before instantiating the session.
        """
        from django.db import connection as db_connection

        with db_connection.schema_editor() as schema_editor:
            try:
                schema_editor.create_model(self._session_model)
            except Exception:
                pass  # Table already exists
            try:
                schema_editor.create_model(self._message_model)
            except Exception:
                pass  # Table already exists

    async def get_items(
        self, limit: int | None = None
    ) -> list[TResponseInputItem]:
        """Retrieve conversation history for this session.

        Args:
            limit: If provided, return only the most recent N items.
                  Items are still returned in chronological order.

        Returns:
            List of conversation items in chronological order.
        """
        queryset = self._message_model.objects.filter(
            session__session_id=self.session_id
        ).order_by("created_at", "id")

        if limit is not None:
            # Get most recent N items, then reverse to chronological order
            queryset = queryset.order_by("-created_at", "-id")[:limit]
            items = [msg.data async for msg in queryset]
            return list(reversed(items))

        return [msg.data async for msg in queryset]

    async def add_items(self, items: list[TResponseInputItem]) -> None:
        """Add new items to the conversation history.

        Args:
            items: List of conversation items to add.
        """
        new_keys: set[str] = set()
        if self._skip_duplicate_items:
            unique_items = []
            for item in items:
                key = self._item_key(item)
                if key in self._added_item_keys or key in new_keys:
                    continue
                new_keys.add(key)
                unique_items.append(item)
            items = unique_items

        if not items:
            return

        # Get or create the session record
        session, _ = await self._session_model.objects.aget_or_create(
            session_id=self.session_id
        )

        # Create message records
        messages = [
            self._message_model(session=session, data=item) for item in items
        ]
        await self._message_model.objects.abulk_create(messages)
        # Remember items only once they are stored, so a failed write can be retried.
        self._added_item_keys.update(new_keys)

    async def pop_item(self) -> TResponseInputItem | None:
        """Remove and return the most recent item from the session.

        Returns:
            The most recent conversation item, or None if the session is empty.
        """

        @sync_to_async
        def _atomic_pop() -> Any | None:
            with transaction.atomic():
                msg = (
                    self._message_model.objects.filter(
                        session__session_id=self.session_id
                    )
                    .order_by("-created_at", "-id")
                    .first()
                )
                if msg is None:
                    return None
                data = msg.data
                msg.delete()
                return data

        item = await _atomic_pop()
        if item is not None and self._skip_duplicate_items:
            self._added_item_keys.discard(self._item_key(item))
        return item

    async def clear_session(self) -> None:
        """Clear all items for this session.

        This deletes messages first, then the session record to respect
        foreign key constraints.
        """
        self._added_item_keys.clear()
        # Delete messages first (respects FK constraints)
        await self._message_model.objects.filter(
            session__session_id=self.session_id
        ).adelete()
        # Then delete the session
        await self._session_model.objects.filter(
            session_id=self.session_id
        ).adelete()
