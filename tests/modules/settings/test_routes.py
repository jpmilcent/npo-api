import importlib.metadata
import sys
from unittest.mock import MagicMock, patch

from fastapi import status
from fastapi.testclient import TestClient
from tests.constants import (
    ERROR_SETTINGS_VERSION_NOT_FOUND,
    ERROR_SETTINGS_WEBSERVICE_NOT_FOUND,
)

from npo.main import app

client = TestClient(app)


def test_settings():
    """Test the frontend settings endpoint."""

    response = client.get("/settings")
    assert response.status_code == status.HTTP_200_OK
    frontend_settings = response.json()

    for key in ["app_name", "zoom_max"]:
        assert key in frontend_settings

    for key in ["database_uri", "admin_email", "uploads_dir", "storage_dir"]:
        assert key not in frontend_settings


async def test_settings_version(client):
    """Test the application version endpoint."""

    mock_version = "1.0.0-test"
    with (
        patch.dict(sys.modules, {"npo.version": None}),
        patch("importlib.metadata.version", return_value=mock_version),
    ):
        response = await client.get("/settings/version")
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/json"
    version_info = response.json()
    assert version_info["version"] == mock_version
    assert version_info["commit_sha"] == "unknown"
    assert version_info["commit_date"] == "unknown"


async def test_settings_version_from_file(client):
    """Test the application version when read from version.py."""

    mock_version = "2.0.0-file+gabcdef.d20231025"
    expected_version = "2.0.0-file"
    mock_commit = "abcdef123"
    mock_module = MagicMock()
    mock_module.version = mock_version
    mock_module.commit_id = mock_commit

    with patch.dict(sys.modules, {"npo.version": mock_module}):
        response = await client.get("/settings/version")
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/json"
    version_info = response.json()
    assert version_info["version"] == expected_version
    assert version_info["commit_sha"] == mock_commit
    assert version_info["commit_date"] == "2023-10-25"


async def test_settings_version_not_found(client):
    """Test the application version when it's not found."""

    package_name = "npo"
    with (
        patch.dict(sys.modules, {"npo.version": None}),
        patch("importlib.metadata.version", side_effect=importlib.metadata.PackageNotFoundError),
    ):
        response = await client.get("/settings/version")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.headers["content-type"] == "application/json"
    version_info = response.json()
    assert "detail" in version_info
    error_detail = version_info["detail"]
    assert error_detail["code"] == ERROR_SETTINGS_VERSION_NOT_FOUND
    assert error_detail["message"] == (
        f"The application version could not be determined for package '{package_name}'. "
        "Check if the package is installed."
    )


async def test_settings_catch_all(verify_404):
    """Test the settings catch-all endpoint for 404 response."""

    unknown_path = "some/random/path"
    await verify_404(
        f"/settings/{unknown_path}",
        ERROR_SETTINGS_WEBSERVICE_NOT_FOUND,
        f"Webservice /settings/{unknown_path} requested not found.",
    )
