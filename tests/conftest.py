import os

import pytest
from tests.fixtures.database import (
    TEST_DATABASE_URL,
    USE_ALEMBIC_MIGRATIONS,
    db_engine,
    override_db_session,
)

# This makes all fixtures in the specified modules available to all tests
pytest_plugins = [
    "tests.fixtures.user",
    "tests.fixtures.settings",
    "tests.fixtures.client",
    "tests.fixtures.data",
    "tests.fixtures.assertions",
]


def pytest_report_header(config):
    messages = []
    if os.path.exists(".env.test"):
        messages.append("⚙️ .env.test file detected.")
    else:
        messages.append("⚙️ No .env.test file found (using default values).")
    messages.append(f"🛢️ TEST_DATABASE_URL: {TEST_DATABASE_URL}")
    messages.append(f"⚗️ USE_ALEMBIC_MIGRATIONS: {USE_ALEMBIC_MIGRATIONS}")
    return messages


def pytest_configure(config):
    """Record the custom marker to avoid warnings."""
    config.addinivalue_line("markers", "integration: mark test as integration test (slow)")


def pytest_collection_modifyitems(items):
    """
    Pytest Hook to change execution order.
    Force tests in 'warmup' directory to be executed first.
    Marks all tests using heavy fixtures as 'integration'.
    """
    items.sort(key=lambda x: 0 if "warmup" in str(x.path) else 1)

    for item in items:
        if "seed_data" in item.fixturenames or "upload_image" in item.fixturenames:
            item.add_marker(pytest.mark.integration)
