from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core import config
from npo.core.database import get_session, init_db


async def test_init_db_calls_alembic_upgrade():
    """
    Test that init_db configure Alembic correctly and launch the 'head' migration.
    """
    with (
        patch("npo.core.database.Config") as MockConfig,
        patch("npo.core.database.command") as mock_command,
    ):
        mock_config_instance = MockConfig.return_value

        await init_db()

        MockConfig.assert_called_once_with(toml_file="pyproject.toml")

        mock_config_instance.set_main_option.assert_called_once_with(
            "sqlalchemy.url", config.settings.database_uri
        )

        mock_command.upgrade.assert_called_once_with(mock_config_instance, "head")


async def test_get_session():
    """
    Test that get_session yields a database session and closes it correctly.
    """
    with patch("npo.core.database.async_sessionmaker") as mock_sessionmaker:
        # Setup the mock session object
        mock_session = AsyncMock(spec=AsyncSession)
        # Configure it as an async context manager (__aenter__ / __aexit__)
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        # Setup the factory returned by sessionmaker
        mock_factory = MagicMock()
        mock_factory.return_value = mock_session
        mock_sessionmaker.return_value = mock_factory

        # Create the generator
        gen = get_session()

        # Get the yielded session using anext()
        yielded_session = await anext(gen)

        # Verify it's our mock
        assert yielded_session is mock_session

        # Verify the session is closed when generator finishes
        with pytest.raises(StopAsyncIteration):
            await anext(gen)

        mock_session.__aexit__.assert_called_once()
