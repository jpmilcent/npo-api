from npo.core import config
from npo.core.dependencies import make_db_directory


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
