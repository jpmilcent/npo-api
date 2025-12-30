from fastapi import status
from fastapi.testclient import TestClient

from npo.main import app

client = TestClient(app)


def test_health_check():
    """Test the health check endpoint."""

    response = client.get("/health/check")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "database": "up",
        "upload_directory": "up",
        "storage_directory": "up",
    }


def test_health_ping():
    """Test the ping route."""

    response = client.get("/health/ping")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"ping": "pong"}
