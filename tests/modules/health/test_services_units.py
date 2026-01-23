from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from npo.modules.health.services import check_database


@pytest.fixture()
def mock_session():
    return AsyncMock()


async def test_check_database_success(mock_session):
    """Verify that the database check returns True on successful query."""
    result = await check_database(mock_session)
    assert result is True
    mock_session.execute.assert_awaited_once()


async def test_check_database_failure(mock_session):
    """Verify that the database check returns False on query failure."""
    # Simulate a database error by making the execute method raise an exception
    mock_session.execute.side_effect = SQLAlchemyError("Database error")

    result = await check_database(mock_session)
    assert result is False
