import os

import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from npo.core.database import Base

# URL for an in-memory SQLite database by default, specific to tests
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
USE_ALEMBIC_MIGRATIONS = os.getenv("USE_ALEMBIC_MIGRATIONS", "0").lower() in ("1", "true", "yes")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine():
    """
    Fixture creating the DB engine and tables once per session.
    """
    # SQLite-specific configuration
    connect_args = {"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {}

    # Create the async engine
    engine = create_async_engine(TEST_DATABASE_URL, connect_args=connect_args)

    # Create tables
    async with engine.begin() as conn:
        # Either run Alembic migrations or create tables from models depending on env.
        if USE_ALEMBIC_MIGRATIONS:

            def upgrade_migration_to_head(connection):
                alembic_cfg = Config(toml_file="pyproject.toml")
                alembic_cfg.attributes["connection"] = connection
                command.upgrade(alembic_cfg, "head")

            await conn.run_sync(upgrade_migration_to_head)
        else:
            # Create tables directly from models (fast, suitable for most unit tests)
            await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Clean up tables (necessary if using a real DB like Postgres)
    async with engine.begin() as conn:
        # Either run Alembic migrations or create tables from models depending on env.
        if USE_ALEMBIC_MIGRATIONS:

            def downgrade_migrations_to_base(connection):
                alembic_cfg = Config(toml_file="pyproject.toml")
                alembic_cfg.attributes["connection"] = connection
                command.downgrade(alembic_cfg, "base")

            await conn.run_sync(downgrade_migrations_to_base)
        else:
            # Drop tables directly from models (fast, suitable for most unit tests)
            await conn.run_sync(Base.metadata.drop_all)

    # Dispose the engine at the end of the test
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def override_db_session(db_engine):
    """
    Fixture that creates a fresh database session for each test.
    Wraps the test in a transaction and rolls it back at the end.
    """
    async with db_engine.connect() as connection:
        # Begin a transaction
        transaction = await connection.begin()

        # Use a nested transaction (SAVEPOINT) to allow app commits without persisting
        await connection.begin_nested()

        # Session factory for tests bound to the connection
        TestingSessionLocal = async_sessionmaker(
            bind=connection,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

        async with TestingSessionLocal() as session:
            yield session

        # Rollback the transaction
        await transaction.rollback()
