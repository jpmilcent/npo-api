import logging
import os
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from npo.core import config
from npo.core.database import Base, get_session
from npo.main import app
from tests.constants import EXTERNAL_FILES

# URL for an in-memory SQLite database by default, specific to tests
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
USE_ALEMBIC_MIGRATIONS = os.getenv("USE_ALEMBIC_MIGRATIONS", "0").lower() in ("1", "true", "yes")

logger = logging.getLogger(__name__)


class MockResponse:
    def __init__(self, json_data, status_code=201):
        self.json_data = json_data
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self.json_data


def pytest_report_header(config):
    messages = []
    if os.path.exists(".env.test"):
        messages.append("⚙️ .env.test file detected.")
    else:
        messages.append("⚙️ No .env.test file found (using default values).")
    messages.append(f"🛢️ TEST_DATABASE_URL: {TEST_DATABASE_URL}")
    messages.append(f"⚗️ USE_ALEMBIC_MIGRATIONS: {USE_ALEMBIC_MIGRATIONS}")
    return messages


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


@pytest.fixture(scope="session")
def override_settings(tmp_path_factory):
    """
    Override configuration to use temporary directories for uploads and storage.
    """
    # Backup original configuration
    original_uploads_dir = config.settings.uploads_dir
    original_storage_dir = config.settings.storage_dir

    # Redirect to an isolated temporary directory (tmp_path_factory for session scope)
    # This avoids writing into tests/data/ and polluting the source tree
    base_path = tmp_path_factory.mktemp("data")
    config.settings.uploads_dir = f"{base_path}/uploads/"
    config.settings.storage_dir = f"{base_path}/storage/"

    yield base_path

    # Restore configuration
    config.settings.uploads_dir = original_uploads_dir
    config.settings.storage_dir = original_storage_dir


@pytest_asyncio.fixture(loop_scope="session")
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


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def session_client(db_engine, override_settings):
    """
    Fixture providing a client that commits changes (for seeding data).
    """
    # Create a session maker that commits (unlike the test one that rolls back)
    SessionLocal = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async def get_session_override():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def seed_data(session_client, large_file_cache):
    """
    Uploads common images once per session and returns their API responses.
    """
    seeded_responses = {}

    for filename, url in EXTERNAL_FILES.items():
        cache_path = large_file_cache / filename

        # Ensure file exists (download logic duplicated here to avoid scope issues)
        if not cache_path.exists():
            logger.info(f"Downloading {filename} from {url} for seeding...")
            with httpx.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()
                with open(cache_path, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)

        # Upload via API
        with open(cache_path, "rb") as f:
            files = {"files": (filename, f, "image/jpeg")}
            response = await session_client.post("/files/upload", files=files)
            if response.status_code == status.HTTP_201_CREATED:
                seeded_responses[filename] = response.json()

    return seeded_responses


@pytest.fixture()
def upload_image(client, shared_datadir, seed_data, request):
    """
    Fixture (Factory function) that provides a function to upload an image and return its hash.
    It uses cached data from seed_data if available to skip the actual upload.
    """
    # Check for marker to set default behavior
    marker = request.node.get_closest_marker("skip_seed")
    default_skip_seed = marker is not None

    async def _uploader(
        image_name,
        return_full_response=False,
        return_response_data=False,
        return_attribute="pixel_hash",
        skip_seed=default_skip_seed,
    ):
        # Check if we have this image pre-loaded
        if not skip_seed and image_name in seed_data:
            # Return a mock response with the pre-calculated data
            response = MockResponse(seed_data[image_name])
        else:
            # Fallback to real upload for non-standard files
            image_path = shared_datadir / image_name
            image_mime = "image/jpeg"

            with open(image_path, "rb") as f:
                files = {"files": (image_name, f, image_mime)}
                response = await client.post("/files/upload", files=files)

        if return_full_response:
            return response
        else:
            assert response.status_code == status.HTTP_201_CREATED, response.json()
            response_data = response.json()
            if return_response_data:
                return response_data
            else:
                assert image_name in response_data
                assert return_attribute in response_data[image_name]
                return response_data[image_name][return_attribute]

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


@pytest.fixture(scope="session")
def large_file_cache():
    """Creates and returns the path to the persistent cache directory."""
    cache_dir = Path(__file__).parent / ".cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir
