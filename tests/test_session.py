"""Tests for DjangoSession."""

import os

import pytest

from openai_django_sessions import DjangoSession


@pytest.fixture
def session(db_tables):
    """Provide a DjangoSession instance for testing."""
    return DjangoSession("test-session")


@pytest.mark.django_db(transaction=True)
class TestDjangoSession:
    """Unit tests for DjangoSession."""

    async def test_add_and_get_items(self, session: DjangoSession) -> None:
        """Test adding and retrieving items."""
        await session.add_items(
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ]
        )

        items = await session.get_items()

        assert len(items) == 2
        assert items[0]["role"] == "user"
        assert items[0]["content"] == "Hello"
        assert items[1]["role"] == "assistant"
        assert items[1]["content"] == "Hi there!"

    async def test_get_items_empty_session(self, session: DjangoSession) -> None:
        """Test getting items from an empty session."""
        items = await session.get_items()
        assert items == []

    async def test_add_empty_items(self, session: DjangoSession) -> None:
        """Test adding empty list of items."""
        await session.add_items([])
        items = await session.get_items()
        assert items == []

    async def test_get_items_with_limit(self, session: DjangoSession) -> None:
        """Test getting items with a limit."""
        await session.add_items(
            [
                {"role": "user", "content": "1"},
                {"role": "user", "content": "2"},
                {"role": "user", "content": "3"},
            ]
        )

        items = await session.get_items(limit=2)

        assert len(items) == 2
        # Should get last 2 items in chronological order
        assert items[0]["content"] == "2"
        assert items[1]["content"] == "3"

    async def test_get_items_limit_exceeds_count(
        self, session: DjangoSession
    ) -> None:
        """Test limit larger than actual items."""
        await session.add_items([{"role": "user", "content": "only one"}])

        items = await session.get_items(limit=10)

        assert len(items) == 1
        assert items[0]["content"] == "only one"

    async def test_pop_item(self, session: DjangoSession) -> None:
        """Test popping the most recent item."""
        await session.add_items(
            [
                {"role": "user", "content": "first"},
                {"role": "user", "content": "second"},
            ]
        )

        item = await session.pop_item()

        assert item is not None
        assert item["content"] == "second"

        # Verify it was removed
        items = await session.get_items()
        assert len(items) == 1
        assert items[0]["content"] == "first"

    async def test_pop_item_empty_session(self, session: DjangoSession) -> None:
        """Test popping from empty session."""
        item = await session.pop_item()
        assert item is None

    async def test_pop_all_items(self, session: DjangoSession) -> None:
        """Test popping all items one by one."""
        await session.add_items([{"role": "user", "content": "test"}])

        item1 = await session.pop_item()
        item2 = await session.pop_item()

        assert item1 is not None
        assert item1["content"] == "test"
        assert item2 is None

    async def test_clear_session(self, session: DjangoSession) -> None:
        """Test clearing all session data."""
        await session.add_items(
            [
                {"role": "user", "content": "one"},
                {"role": "user", "content": "two"},
            ]
        )

        await session.clear_session()

        items = await session.get_items()
        assert items == []

    async def test_clear_empty_session(self, session: DjangoSession) -> None:
        """Test clearing an already empty session."""
        await session.clear_session()
        items = await session.get_items()
        assert items == []

    async def test_multiple_sessions_isolated(self, db_tables) -> None:
        """Test that different session IDs are isolated."""
        session1 = DjangoSession("session-1")
        session2 = DjangoSession("session-2")

        await session1.add_items([{"role": "user", "content": "session 1 msg"}])
        await session2.add_items([{"role": "user", "content": "session 2 msg"}])

        items1 = await session1.get_items()
        items2 = await session2.get_items()

        assert len(items1) == 1
        assert items1[0]["content"] == "session 1 msg"
        assert len(items2) == 1
        assert items2[0]["content"] == "session 2 msg"

    async def test_from_settings_class_method(self, db_tables) -> None:
        """Test the from_settings class method."""
        session = DjangoSession.from_settings("test-from-settings")

        await session.add_items([{"role": "user", "content": "test"}])
        items = await session.get_items()

        assert len(items) == 1

    async def test_chronological_order_preserved(
        self, session: DjangoSession
    ) -> None:
        """Test that items are always returned in chronological order."""
        # Add items in separate calls to ensure different timestamps
        await session.add_items([{"role": "user", "content": "first"}])
        await session.add_items([{"role": "assistant", "content": "second"}])
        await session.add_items([{"role": "user", "content": "third"}])

        items = await session.get_items()

        assert len(items) == 3
        assert items[0]["content"] == "first"
        assert items[1]["content"] == "second"
        assert items[2]["content"] == "third"


@pytest.mark.django_db(transaction=True)
class TestCustomTables:
    """Tests for custom table names."""

    def test_custom_table_names(self) -> None:
        """Test using custom table names (sync for create_tables)."""
        import asyncio
        from django.db import connection

        session = DjangoSession(
            "custom-tables",
            sessions_table="custom_sessions",
            messages_table="custom_messages",
            create_tables=True,
        )

        # Run async operations via asyncio.run
        async def run_test():
            await session.add_items([{"role": "user", "content": "custom"}])
            items = await session.get_items()
            assert len(items) == 1
            assert items[0]["content"] == "custom"
            await session.clear_session()

        asyncio.run(run_test())

        # Cleanup custom tables
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS custom_messages")
            cursor.execute("DROP TABLE IF EXISTS custom_sessions")


@pytest.mark.django_db(transaction=True)
class TestCreateTables:
    """Tests for create_tables functionality."""

    def test_create_tables_flag(self) -> None:
        """Test that create_tables creates tables when needed (sync context)."""
        from django.db import connection

        # Use unique table names to avoid conflicts
        session = DjangoSession(
            "create-tables-test",
            sessions_table="test_auto_sessions",
            messages_table="test_auto_messages",
            create_tables=True,
        )

        # Verify tables were created by checking we can query
        assert session._session_model.objects.count() == 0

        # Cleanup
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS test_auto_messages")
            cursor.execute("DROP TABLE IF EXISTS test_auto_sessions")


@pytest.mark.django_db(transaction=True)
class TestIntegration:
    """Integration tests with the OpenAI Agents SDK."""

    @pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY not set",
    )
    async def test_with_agent(self, db_tables) -> None:
        """Integration test with actual OpenAI agent."""
        from agents import Agent, Runner

        session = DjangoSession("integration-test")
        agent = Agent(name="test-agent", instructions="Be brief. Reply in one word.")

        result = await Runner.run(agent, "Say hello", session=session)

        assert result.final_output

        # Verify session persisted
        items = await session.get_items()
        assert len(items) >= 2  # At least user message + assistant response
