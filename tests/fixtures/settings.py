from unittest.mock import patch

import pytest

from npo.core import config
from npo.core.dependencies import ensure_system_directories

# Clé de 32 octets pour éviter le warning InsecureKeyLengthWarning dans tous les tests
TEST_SECRET_KEY = "test_secret_key_" * 2


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

    # Ensure directories exist
    ensure_system_directories()

    yield base_path

    # Restore configuration
    config.settings.uploads_dir = original_uploads_dir
    config.settings.storage_dir = original_storage_dir


@pytest.fixture(autouse=True)
def mock_gettext():
    """
    Global fixture to mock the translation function '_' to avoid ContextVar errors
    outside of the request context (fastapi-babel).
    """
    with patch("npo.core.constants._", side_effect=lambda x: x):
        yield


@pytest.fixture(scope="session", autouse=True)
def mock_secret_key():
    """
    Patch globalement SECRET_KEY dans le module security pour utiliser une clé sécurisée.
    """
    with patch("npo.core.security.SECRET_KEY", TEST_SECRET_KEY):
        yield
