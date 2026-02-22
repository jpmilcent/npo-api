import httpx
import pytest
from fastapi import status


@pytest.fixture()
def verify_404(client, verify_404_response):
    async def _verify(url: str, expected_code: str, expected_message: str):
        response = await client.get(url)
        verify_404_response(response, expected_code, expected_message)

    return _verify


@pytest.fixture()
def verify_404_response():
    def _verify(response: httpx.Response, expected_code: str, expected_message: str):
        assert isinstance(response, httpx.Response)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.headers["content-type"] == "application/json"
        data = response.json()
        assert "detail" in data
        error_detail = data["detail"]
        assert error_detail["code"] == expected_code
        assert error_detail["message"] == expected_message

    return _verify
