"""Dependency management for NPO application."""

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy.engine import make_url

from npo import config


@lru_cache
def get_frontend_settings():
    """Return frontend settings as a singleton."""
    return config.frontend_settings


def make_upload_directory():
    """Ensure the upload directory exists."""
    if not os.path.exists(config.settings.uploads_dir):
        os.makedirs(config.settings.uploads_dir, exist_ok=True)


def make_storage_directory():
    """Ensure the storage directory exists."""
    if not os.path.exists(config.settings.storage_dir):
        os.makedirs(config.settings.storage_dir, exist_ok=True)


def make_db_directory():
    """Ensure the db directory exists if we use SQLite.
    If we are using sqlite and it's a file based database,
    we need to make sure the directory exists.
    """
    db_uri = config.settings.database_uri
    url = make_url(db_uri)
    if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
        db_path = Path(url.database)
        db_path.parent.mkdir(parents=True, exist_ok=True)
