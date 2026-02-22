from datetime import timedelta

import pytest
from fastapi import status

from npo.core.security import create_refresh_token, decode_access_token


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
