from fastapi import status
from fastapi.testclient import TestClient

from npo.main import app

client = TestClient(app)


def test_settings():
    """Test the frontend settings endpoint."""

    response = client.get("/settings")
    assert response.status_code == status.HTTP_200_OK
    frontend_settings = response.json()

    for key in ["app_name", "zoom_max"]:
        assert key in frontend_settings.keys()

    for key in ["database_uri", "admin_email", "uploads_dir", "storage_dir"]:
        assert key not in frontend_settings.keys()
