"""Pytest configuration with minimal Django setup."""

import os

# Configure Django BEFORE any imports that might need it
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")


def pytest_configure() -> None:
    """Configure Django settings before tests run."""
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
            ],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
        )

    import django

    django.setup()


# Import pytest AFTER Django setup can be guaranteed by pytest_configure
import pytest


@pytest.fixture
def db_tables():
    """Create and teardown database tables for tests."""
    from django.db import connection

    from openai_django_sessions.models import AgentMessage, AgentSession

    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(AgentSession)
        schema_editor.create_model(AgentMessage)

    yield

    with connection.schema_editor() as schema_editor:
        schema_editor.delete_model(AgentMessage)
        schema_editor.delete_model(AgentSession)


@pytest.fixture
def session(db_tables):
    """Provide a DjangoSession instance for testing."""
    from openai_django_sessions import DjangoSession

    return DjangoSession("test-session")
