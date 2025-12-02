# openai-django-sessions

Django ORM-based session backend for the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python).

Store your agent conversation history in any Django-supported database (PostgreSQL, MySQL, SQLite, etc.) with full async support.

## Installation

```bash
pip install openai-django-sessions
```

## Requirements

- Python 3.12+
- Django 5.0+
- openai-agents 0.1.0+

## Quick Start

```python
from agents import Agent, Runner
from openai_django_sessions import DjangoSession

async def chat():
    # Create a session (auto-creates tables in development)
    session = DjangoSession("user-123", create_tables=True)

    agent = Agent(name="Assistant", instructions="You are a helpful assistant.")

    # First message
    result = await Runner.run(agent, "Hello!", session=session)
    print(result.final_output)

    # Follow-up (session maintains conversation history)
    result = await Runner.run(agent, "What did I just say?", session=session)
    print(result.final_output)
```

## Usage

### Basic Usage

```python
from openai_django_sessions import DjangoSession

# Simple instantiation
session = DjangoSession("user-123")

# With auto table creation (for development/testing)
session = DjangoSession("user-123", create_tables=True)
```

### Custom Table Names

```python
session = DjangoSession(
    "user-123",
    sessions_table="my_agent_sessions",
    messages_table="my_agent_messages",
    create_tables=True,
)
```

### Using with Django Settings

```python
# Semantic alias that uses Django's configured database
session = DjangoSession.from_settings("user-123", create_tables=True)
```

## API Reference

### DjangoSession

```python
class DjangoSession(SessionABC):
    def __init__(
        self,
        session_id: str,
        *,
        sessions_table: str = "agent_sessions",
        messages_table: str = "agent_messages",
        create_tables: bool = False,
    ) -> None: ...

    @classmethod
    def from_settings(
        cls,
        session_id: str,
        *,
        sessions_table: str = "agent_sessions",
        messages_table: str = "agent_messages",
        create_tables: bool = False,
    ) -> DjangoSession: ...

    async def get_items(self, limit: int | None = None) -> list[TResponseInputItem]: ...
    async def add_items(self, items: list[TResponseInputItem]) -> None: ...
    async def pop_item(self) -> TResponseInputItem | None: ...
    async def clear_session(self) -> None: ...
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session_id` | `str` | required | Unique identifier for the conversation session |
| `sessions_table` | `str` | `"agent_sessions"` | Database table name for session metadata |
| `messages_table` | `str` | `"agent_messages"` | Database table name for conversation messages |
| `create_tables` | `bool` | `False` | Auto-create tables if they don't exist (dev/test only) |

### Methods

| Method | Description |
|--------|-------------|
| `get_items(limit=None)` | Retrieve conversation history. If `limit` is set, returns the N most recent items in chronological order. |
| `add_items(items)` | Add new items to conversation history. |
| `pop_item()` | Remove and return the most recent item, or `None` if empty. |
| `clear_session()` | Delete all items and session record. |

## Database Schema

The library creates two tables:

### agent_sessions

| Column | Type | Description |
|--------|------|-------------|
| `id` | BigAutoField | Primary key |
| `session_id` | CharField(255) | Unique session identifier (indexed) |
| `created_at` | DateTimeField | Session creation timestamp |
| `updated_at` | DateTimeField | Last update timestamp |

### agent_messages

| Column | Type | Description |
|--------|------|-------------|
| `id` | BigAutoField | Primary key |
| `session_id` | ForeignKey | Reference to agent_sessions |
| `data` | JSONField | Conversation item data |
| `created_at` | DateTimeField | Message creation timestamp |

## Production Setup

For production, create the tables using Django migrations or raw SQL instead of `create_tables=True`:

```sql
CREATE TABLE agent_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_agent_sessions_session_id ON agent_sessions(session_id);

CREATE TABLE agent_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_agent_messages_session_id ON agent_messages(session_id);
```

## Similar Projects

- [SQLAlchemySession](https://openai.github.io/openai-agents-python/sessions/sqlalchemy_session/) - SQLAlchemy-based session for the OpenAI Agents SDK

## License

MIT
