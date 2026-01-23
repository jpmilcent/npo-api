from unittest.mock import AsyncMock, patch

from fastapi import status


async def test_health_check(client):
    """Test the health check endpoint."""

    response = await client.get("/health/check")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "database": "up",
        "upload_directory": "up",
        "storage_directory": "up",
    }


async def test_check_health_degraded(client):
    """Test the health check endpoint when services are down."""
    with (
        patch("npo.modules.health.routes.check_database", new_callable=AsyncMock) as mock_db,
        patch(
            "npo.modules.health.routes.check_upload_directory", new_callable=AsyncMock
        ) as mock_upload,
        patch(
            "npo.modules.health.routes.check_storage_directory", new_callable=AsyncMock
        ) as mock_storage,
    ):
        mock_db.return_value = False
        mock_upload.return_value = False
        mock_storage.return_value = False

        response = await client.get("/health/check")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "database": "down",
            "upload_directory": "down",
            "storage_directory": "down",
        }


async def test_health_ping(client):
    """Test the ping route."""

    response = await client.get("/health/ping")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"ping": "pong"}
