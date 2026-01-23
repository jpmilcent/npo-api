import logging
from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from npo.main import app


def test_lifespan_logs(caplog):
    """
    Test that the logs of startup and shutdown are properly emitted by the lifespan function.
    """
    caplog.set_level(logging.INFO)

    with patch("npo.main.init_db", new_callable=AsyncMock) as mock_init_db:
        with TestClient(app):
            # At this stage, the code before the 'yield' has been executed
            assert "✅ Application started and database tables created!" in caplog.text

            # Check that the DB was properly initialized (called)
            mock_init_db.assert_awaited_once()

        # Outside the 'with' block, the shutdown is triggered (code after the 'yield')
        assert "🛑 Application shutting down!" in caplog.text


def test_main_page():
    """
    Test that the main page returns a 200 status code.
    """
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert (
        b'<form action="/images/upload" enctype="multipart/form-data" method="post">'
        in response.content
    )
    assert b'<input name="files" type="file" multiple>' in response.content
