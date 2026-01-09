import logging
import os
import shutil
from pathlib import Path

import httpx
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
EXTERNAL_FILES_DIR = "https://github.com/jpmilcent/npo-api/releases/download/v0.0.1-alpha"
# Dictionary of external files: Name -> URL
EXTERNAL_FILES = {
    "image_03.dng": f"{EXTERNAL_FILES_DIR}/image_03.dng",
    "image_04.dng": f"{EXTERNAL_FILES_DIR}/image_04.dng",
    "image_05.nef": f"{EXTERNAL_FILES_DIR}/image_05.nef",
    "image_06.nef": f"{EXTERNAL_FILES_DIR}/image_06.nef",
}

logger = logging.getLogger(__name__)


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
    config.settings.storage_dir = f"{tmp_path}/storage/"

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

    async def _uploader(
        image_name,
        return_full_response=False,
        return_response_data=False,
        return_attribute="pixel_hash",
    ):
        image_path = shared_datadir / image_name
        image_mime = "image/jpeg"

        # Upload the file
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


@pytest.fixture()
def ensure_large_files(shared_datadir, large_file_cache):
    """
    Fixture that ensures the requested files are present in shared_datadir.
    It downloads them to the cache if necessary, then copies them to the test directory.
    This prevents pytest-datadir from copying all files present
    in tests/data to shared_datadir (temporary directory) during each test session.
    """

    def _ensure(filenames):
        for filename in filenames:
            if filename not in EXTERNAL_FILES:
                continue

            cache_path = large_file_cache / filename

            # Download if not in cache
            if not cache_path.exists():
                url = EXTERNAL_FILES[filename]
                logger.info(f"Downloading {filename} from {url}...")
                with httpx.stream("GET", url, follow_redirects=True) as response:
                    response.raise_for_status()
                    with open(cache_path, "wb") as f:
                        for chunk in response.iter_bytes():
                            f.write(chunk)

            # Copy from cache to temporary directory for test (shared_datadir)
            dest_path = shared_datadir / filename
            if not dest_path.exists():
                shutil.copy(cache_path, dest_path)

    return _ensure
