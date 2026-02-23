from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.responses import RedirectResponse
from tests.constants import (
    ERROR_AUTH_PROVIDER_NOT_FOUND,
    ERROR_NO_EMAIL_AUTH_ERROR,
    ERROR_NO_USER_INFO_AUTH_ERROR,
    ERROR_NOT_VERIFIED_EMAIL_AUTH_ERROR,
)

from npo.core.security import create_refresh_token, decode_access_token


@pytest.mark.asyncio
async def test_login_success(client, test_user_data):
    """
    Verifies that a user can log in with valid credentials.
    """
    login_data = {
        "username": test_user_data["email"],
        "password": test_user_data["password"],
    }
    response = await client.post("/auth/login", data=login_data)
    assert response.status_code == status.HTTP_200_OK
    tokens = response.json()

    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client, test_user_data):
    """
    Verifies that login fails with invalid password.
    """
    login_data = {
        "username": test_user_data["email"],
        "password": "wrongpassword",
    }
    response = await client.post("/auth/login", data=login_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_token_success(client, test_user_data):
    """
    Verifies that a valid refresh token allows obtaining a new access token.
    """
    # 1. Manual login to retrieve the refresh_token
    login_data = {
        "username": test_user_data["email"],
        "password": test_user_data["password"],
    }
    login_response = await client.post("/auth/login", data=login_data)
    assert login_response.status_code == status.HTTP_200_OK
    tokens = login_response.json()

    refresh_token = tokens.get("refresh_token")
    assert refresh_token is not None, "The refresh token is missing from the login response"
    original_access_token = tokens.get("access_token")

    # 2. Call the refresh endpoint
    refresh_response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert refresh_response.status_code == status.HTTP_200_OK
    new_tokens = refresh_response.json()

    # 3. Verifications
    assert "access_token" in new_tokens
    assert new_tokens["access_token"] != original_access_token
    assert new_tokens["token_type"] == "bearer"

    # Verify that the new access token contains the expected claims
    payload = decode_access_token(new_tokens["access_token"])
    assert "iat" in payload
    assert "jti" in payload


@pytest.mark.asyncio
async def test_refresh_token_invalid(client):
    """
    Verifies that the API rejects an invalid or malformed refresh token.
    """
    response = await client.post("/auth/refresh", json={"refresh_token": "invalid.token.value"})
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.asyncio
async def test_refresh_token_expired(client):
    """
    Verifies that the API rejects an expired refresh token.
    """
    # Create a token that expired 1 second ago
    expired_token = create_refresh_token(
        data={"sub": "test@example.com"}, expires_delta=timedelta(seconds=-1)
    )

    response = await client.post("/auth/refresh", json={"refresh_token": expired_token})
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client, test_user_data):
    """
    Verifies that logging out invalidates the refresh token.
    """
    # 1. Login to get a fresh pair of tokens
    login_data = {
        "username": test_user_data["email"],
        "password": test_user_data["password"],
    }
    response = await client.post("/auth/login", data=login_data)
    assert response.status_code == status.HTTP_200_OK
    tokens = response.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # 2. Logout using the access token
    # We explicitly set the header here to ensure we are using the token associated
    # with the refresh token we just got (to be precise about the session).
    logout_response = await client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert logout_response.status_code == status.HTTP_204_NO_CONTENT

    # 3. Attempt to refresh the token
    refresh_response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})

    # 4. Verify it is rejected
    # The server should reject it because the JTI stored in DB has been cleared/changed
    assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_token_rotation(client, test_user_data):
    """
    Verifies that the refresh token is rotated (new JTI) on use,
    and the old one becomes invalid.
    """
    # 1. Login
    login_data = {
        "username": test_user_data["email"],
        "password": test_user_data["password"],
    }
    response = await client.post("/auth/login", data=login_data)
    assert response.status_code == status.HTTP_200_OK
    tokens = response.json()
    refresh_token_1 = tokens["refresh_token"]

    # Decode to get JTI 1
    payload_1 = decode_access_token(refresh_token_1)
    jti_1 = payload_1["jti"]

    # 2. Refresh
    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token_1})
    assert response.status_code == status.HTTP_200_OK
    new_tokens = response.json()
    refresh_token_2 = new_tokens["refresh_token"]

    # Decode to get JTI 2
    payload_2 = decode_access_token(refresh_token_2)
    jti_2 = payload_2["jti"]

    # 3. Verify JTI changed
    assert jti_1 != jti_2
    assert refresh_token_1 != refresh_token_2

    # 4. Verify old refresh token is now invalid (because JTI in DB has been updated)
    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token_1})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_token_reuse_detection_invalidates_all_sessions(client, test_user_data):
    """
    Verifies that reusing an old refresh token triggers reuse detection,
    which in turn invalidates all active sessions for that user.
    """
    # 1. Login to get the first set of tokens
    login_data = {
        "username": test_user_data["email"],
        "password": test_user_data["password"],
    }
    response = await client.post("/auth/login", data=login_data)
    assert response.status_code == status.HTTP_200_OK
    tokens_1 = response.json()
    refresh_token_1 = tokens_1["refresh_token"]

    # 2. Use the first refresh token to get a second set (normal rotation)
    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token_1})
    assert response.status_code == status.HTTP_200_OK
    tokens_2 = response.json()
    refresh_token_2 = tokens_2["refresh_token"]

    # At this point, refresh_token_1 is old, and refresh_token_2 is the current valid one.

    # 3. Attempt to reuse the old refresh_token_1. This should be rejected.
    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token_1})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # 4. Verify that the reuse detection has invalidated all tokens.
    # The currently valid refresh_token_2 should now also be invalid.
    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token_2})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_login_provider_redirect(client):
    """
    Verifies that the login provider route redirects to the provider.
    """
    provider = "github"
    mock_client = AsyncMock()
    target_url = "https://github.com/login/oauth/authorize"
    # Simulate the RedirectResponse returned by authlib
    mock_client.authorize_redirect.return_value = RedirectResponse(url=target_url)

    with patch(
        "npo.modules.auth.routes.oauth.create_client", return_value=mock_client
    ) as mock_create_client:
        # follow_redirects=False allows us to inspect the 307 response instead of following it
        response = await client.get(f"/auth/providers/{provider}/login", follow_redirects=False)

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert response.headers["location"] == target_url
        mock_create_client.assert_called_with(provider)
        mock_client.authorize_redirect.assert_called_once()


@pytest.mark.asyncio
async def test_login_provider_not_found(client):
    """
    Verifies that an invalid provider returns 404.
    """
    provider = "invalid-provider"
    with patch("npo.modules.auth.routes.oauth.create_client", return_value=None):
        response = await client.get(f"/auth/providers/{provider}/login")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_auth_provider_callback_success(client):
    """
    Verifies that the OAuth2 callback creates a user (or logs them in) and returns tokens.
    """
    provider = "github"
    mock_client = AsyncMock()
    # Simulate a successful token exchange
    mock_client.authorize_access_token.return_value = {"access_token": "dummy_token"}

    # Simulate user info returned by the service
    user_info = {
        "sub": "123456",
        "email": "oauth_user@example.com",
        "email_verified": True,
        "picture_url": "http://example.com/avatar.jpg",
        "given_name": "OAuth",
        "family_name": "User",
        "name": "OAuth User",
    }

    with (
        patch("npo.modules.auth.routes.oauth.create_client", return_value=mock_client),
        patch("npo.modules.auth.routes.get_oauth_user_info", return_value=user_info),
    ):
        response = await client.get(f"/auth/providers/{provider}/callback")

        assert response.status_code == status.HTTP_200_OK
        tokens = response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_auth_provider_callback_no_email(client):
    """
    Verifies that the callback rejects users with no email.
    """
    provider = "github"
    mock_client = AsyncMock()
    mock_client.authorize_access_token.return_value = {"access_token": "dummy_token"}

    user_info = {
        "sub": "123456",
        "email": None,
        "email_verified": False,
        "picture_url": "http://example.com/avatar.jpg",
    }

    with (
        patch("npo.modules.auth.routes.oauth.create_client", return_value=mock_client),
        patch("npo.modules.auth.routes.get_oauth_user_info", return_value=user_info),
    ):
        response = await client.get(f"/auth/providers/{provider}/callback")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_details = response.json()["detail"]
        assert error_details["code"] == ERROR_NO_EMAIL_AUTH_ERROR
        assert error_details["message"] == f"Email not found in {provider} user info"


@pytest.mark.asyncio
async def test_auth_provider_callback_email_not_verified(client):
    """
    Verifies that the callback rejects users with unverified emails.
    """
    provider = "github"
    mock_client = AsyncMock()
    mock_client.authorize_access_token.return_value = {"access_token": "dummy_token"}

    user_info = {
        "sub": "123456",
        "email": "unverified@example.com",
        "email_verified": False,
        "picture_url": "http://example.com/avatar.jpg",
    }

    with (
        patch("npo.modules.auth.routes.oauth.create_client", return_value=mock_client),
        patch("npo.modules.auth.routes.get_oauth_user_info", return_value=user_info),
    ):
        response = await client.get(f"/auth/providers/{provider}/callback")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_details = response.json()["detail"]
        assert error_details["code"] == ERROR_NOT_VERIFIED_EMAIL_AUTH_ERROR
        assert error_details["message"] == f"Email not verified by {provider}."


@pytest.mark.asyncio
async def test_auth_provider_callback_no_user_info(client):
    """
    Verifies that the callback handles cases where no user info is returned.
    """
    provider = "github"
    mock_client = AsyncMock()
    mock_client.authorize_access_token.return_value = {"access_token": "dummy_token"}

    with (
        patch("npo.modules.auth.routes.oauth.create_client", return_value=mock_client),
        patch("npo.modules.auth.routes.get_oauth_user_info", return_value={}),
    ):
        response = await client.get(f"/auth/providers/{provider}/callback")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_details = response.json()["detail"]
        assert error_details["code"] == ERROR_NO_USER_INFO_AUTH_ERROR
        assert error_details["message"] == f"No user info returned from {provider}"


@pytest.mark.asyncio
async def test_auth_provider_callback_no_user(client):
    """
    Verifies that the callback handles cases where no user is returned.
    """
    provider = "github"

    with (
        patch("npo.modules.auth.routes.oauth.create_client", return_value=None),
        patch("npo.modules.auth.routes.get_oauth_user_info", return_value={}),
    ):
        response = await client.get(f"/auth/providers/{provider}/callback")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        error_details = response.json()["detail"]
        assert error_details["code"] == ERROR_AUTH_PROVIDER_NOT_FOUND
        assert error_details["message"] == f"Provider '{provider}' not found."


@pytest.mark.asyncio
async def test_refresh_token_inactive_user(client, test_user_data):
    """
    Verifies that an inactive user cannot refresh their token.
    """
    # 1. Login to get a refresh token
    login_data = {
        "username": test_user_data["email"],
        "password": test_user_data["password"],
    }
    response = await client.post("/auth/login", data=login_data)
    refresh_token = response.json()["refresh_token"]

    # 2. Mock get_user_by_uid to return an inactive user
    mock_user = AsyncMock()
    mock_user.is_active = False

    with patch("npo.modules.auth.routes.get_user_by_uid", new_callable=AsyncMock) as mock_get_user:
        mock_get_user.return_value = mock_user
        response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_token_user_not_found(client, test_user_data):
    """
    Verifies that if the user is not found (e.g. deleted), refresh fails.
    """
    # 1. Login
    login_data = {
        "username": test_user_data["email"],
        "password": test_user_data["password"],
    }
    response = await client.post("/auth/login", data=login_data)
    refresh_token = response.json()["refresh_token"]

    # 2. Mock get_user_by_uid to return None
    with patch("npo.modules.auth.routes.get_user_by_uid", new_callable=AsyncMock) as mock_get_user:
        mock_get_user.return_value = None
        response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_logout_exception_handling(client, test_user_data):
    """
    Verifies that logout returns 204 even if an internal exception occurs during revocation.
    """
    # 1. Login
    login_data = {
        "username": test_user_data["email"],
        "password": test_user_data["password"],
    }
    response = await client.post("/auth/login", data=login_data)
    access_token = response.json()["access_token"]

    # 2. Mock User.revoke_refresh_token to raise an exception
    with patch(
        "npo.modules.users.models.User.revoke_refresh_token", side_effect=Exception("DB Error")
    ):
        response = await client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_auth_provider_callback_token_error(client):
    """
    Verifies that if the provider token exchange fails, a 401 is returned.
    """
    provider = "github"
    mock_client = AsyncMock()
    mock_client.authorize_access_token.side_effect = Exception("Token exchange failed")

    with patch("npo.modules.auth.routes.oauth.create_client", return_value=mock_client):
        response = await client.get(f"/auth/providers/{provider}/callback")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_auth_catch_all(client):
    """
    Verifies that the catch-all route returns 404 for unknown auth paths.
    """
    response = await client.get("/auth/some/random/path")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_refresh_token_wrong_type(client, test_user_data):
    """
    Verifies that using an access token (which lacks type='refresh') as a refresh token fails.
    """
    # 1. Login to get an access token
    login_data = {
        "username": test_user_data["email"],
        "password": test_user_data["password"],
    }
    response = await client.post("/auth/login", data=login_data)
    access_token = response.json()["access_token"]

    # 2. Attempt refresh with access token
    response = await client.post("/auth/refresh", json={"refresh_token": access_token})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    error_details = response.json()["detail"]
    assert error_details["code"] == "REFRESH_AUTH_ERROR"
