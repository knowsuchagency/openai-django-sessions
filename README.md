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

### Running Several Agents on One Session

Each `Runner.run` call stores its input in the session. When you run several agents in turn on the
same session with the same user message (for example a triage agent followed by a router agent),
that message is stored once per run. Pass `skip_duplicate_items=True` to have `add_items` skip any
item identical to one the same `DjangoSession` instance already added:

```python
session = DjangoSession("user-123", skip_duplicate_items=True)

result = await Runner.run(triage_agent, user_message, session=session)
result = await Runner.run(router_agent, user_message, session=session)  # message stored once
```

The check is per instance, so create one `DjangoSession` per request or turn. With the option on,
identical items added through the same instance are stored once, so a user repeating the exact same
message later in that instance's lifetime is stored once too.

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
        skip_duplicate_items: bool = False,
    ) -> None: ...

    @classmethod
    def from_settings(
        cls,
        session_id: str,
        *,
        sessions_table: str = "agent_sessions",
        messages_table: str = "agent_messages",
        create_tables: bool = False,
        skip_duplicate_items: bool = False,
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
| `skip_duplicate_items` | `bool` | `False` | Skip items identical to one this instance already added |

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
