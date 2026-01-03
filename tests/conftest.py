import os

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from npo import config
from npo.database import Base, get_session
from npo.main import app

# URL for an in-memory SQLite database by default, specific to tests
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
USE_ALEMBIC_MIGRATIONS = os.getenv("USE_ALEMBIC_MIGRATIONS", "0").lower() in ("1", "true", "yes")


def pytest_report_header(config):
    messages = []
    if os.path.exists(".env.test"):
        messages.append("⚙️ .env.test file detected.")
    else:
        messages.append("⚙️ No .env.test file found (using default values).")
    messages.append(f"🛢️ TEST_DATABASE_URL: {TEST_DATABASE_URL}")
    messages.append(f"⚗️ USE_ALEMBIC_MIGRATIONS: {USE_ALEMBIC_MIGRATIONS}")
    return messages


@pytest_asyncio.fixture
async def override_db_session():
    """
    Fixture that creates a fresh database for each test.
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

    # Session factory for tests
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

    async with TestingSessionLocal() as session:
        yield session

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


@pytest_asyncio.fixture
def override_settings(tmp_path):
    """
    Override configuration to use temporary directories for uploads and storage.
    """
    # Backup original configuration
    original_uploads_dir = config.settings.uploads_dir
    original_storage_dir = config.settings.storage_dir

    # Redirect to an isolated temporary directory (tmp_path)
    # This avoids writing into tests/data/ and polluting the source tree
    config.settings.uploads_dir = f"{tmp_path}/uploads/"
    # os.makedirs(config.settings.uploads_dir, exist_ok=True)
    config.settings.storage_dir = f"{tmp_path}/storage/"
    # os.makedirs(config.settings.storage_dir, exist_ok=True)

    yield tmp_path

    # Restore configuration
    config.settings.uploads_dir = original_uploads_dir
    config.settings.storage_dir = original_storage_dir


@pytest_asyncio.fixture
async def client(override_db_session, override_settings):
    """
    Fixture providing a real async HTTP client.
    Overrides the application's database dependency.
    """
    # Override the get_session dependency to use the test session
    app.dependency_overrides[get_session] = lambda: override_db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    # Clear dependency overrides after the test
    app.dependency_overrides.clear()


@pytest.fixture()
def upload_image(client, shared_datadir):
    """
    Fixture (Factory function) that provides a function to upload an image and return its hash.
    """

    async def _uploader(image_name):
        image_path = shared_datadir / image_name
        image_mime = "image/jpeg"

        # Upload the file
        with open(image_path, "rb") as f:
            files = {"files": (image_name, f, image_mime)}
            response = await client.post("/files/upload", files=files)

        assert response.status_code == status.HTTP_201_CREATED

        # Return the pixel hash of the uploaded file
        return response.json()[image_name]["pixel_hash"]

    return _uploader


@pytest.fixture()
def verify_404(client):
    async def _verify(url: str, expected_code: str, expected_message: str):
        response = await client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert "detail" in data
        error_detail = data["detail"]
        assert error_detail["code"] == expected_code
        assert error_detail["message"] == expected_message

    return _verify
