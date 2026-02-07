from npo.core import config
from npo.core.dependencies import (
    ensure_system_directories,
    make_db_directory,
    make_storage_directory,
    make_upload_directory,
)


def test_make_db_directory_sqlite_file(tmp_path):
    """
    Test that make_db_directory creates the directory for a file-based SQLite database.
    """
    db_file = tmp_path / "subdir" / "test.db"
    db_uri = f"sqlite:///{db_file}"

    # Patch the config to use our test database URI
    original_db_uri = config.settings.database_uri
    config.settings.database_uri = db_uri

    try:
        make_db_directory()
        assert db_file.parent.exists(), "The database directory should have been created."
    finally:
        # Restore original database URI
        config.settings.database_uri = original_db_uri


def test_make_upload_directory(tmp_path):
    """Test that make_upload_directory creates the uploads directory."""
    upload_dir = str(tmp_path / "uploads")

    original_uploads_dir = config.settings.uploads_dir
    config.settings.uploads_dir = upload_dir

    try:
        make_upload_directory()
        assert (tmp_path / "uploads").exists()
    finally:
        config.settings.uploads_dir = original_uploads_dir


def test_make_storage_directory(tmp_path):
    """Test that make_storage_directory creates the storage directory."""
    storage_dir = str(tmp_path / "storage")

    original_storage_dir = config.settings.storage_dir
    config.settings.storage_dir = storage_dir

    try:
        make_storage_directory()
        assert (tmp_path / "storage").exists()
    finally:
        config.settings.storage_dir = original_storage_dir


def test_ensure_system_directories(tmp_path):
    """Test that ensure_system_directories creates all required directories."""
    db_file = tmp_path / "db" / "test.db"
    db_uri = f"sqlite:///{db_file}"
    upload_dir = str(tmp_path / "uploads")
    storage_dir = str(tmp_path / "storage")

    original_db_uri = config.settings.database_uri
    original_uploads_dir = config.settings.uploads_dir
    original_storage_dir = config.settings.storage_dir

    config.settings.database_uri = db_uri
    config.settings.uploads_dir = upload_dir
    config.settings.storage_dir = storage_dir

    try:
        ensure_system_directories()
        assert db_file.parent.exists()
        assert (tmp_path / "uploads").exists()
        assert (tmp_path / "storage").exists()
    finally:
        config.settings.database_uri = original_db_uri
        config.settings.uploads_dir = original_uploads_dir
        config.settings.storage_dir = original_storage_dir
