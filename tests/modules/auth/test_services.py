from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jwt import InvalidTokenError
from tests.constants import ERROR_INACTIVE_USER_ERROR, ERROR_UNAUTHORIZED_USER_ERROR

from npo.modules.auth.exceptions import InactiveUserError, UnauthorizedUserError
from npo.modules.auth.services import (
    authenticate_user,
    extract_name_parts,
    get_current_active_user,
    get_current_user,
    get_email_from_provider,
    get_oauth_user_info,
)


@pytest.mark.asyncio
async def test_authenticate_user_return_none(override_db_session):
    sub = "fake_username"
    password = "fake_password"
    with patch("npo.modules.auth.services.get_user_by_email") as mock_get_user:
        mock_get_user.return_value = None
        out = await authenticate_user(override_db_session, sub, password)

    assert out is None


@pytest.mark.asyncio
async def test_authenticate_user_return_user(override_db_session):
    sub = "fake_username"
    password = "fake_password"
    user = MagicMock()
    user.password = "hashed_password"

    with patch("npo.modules.auth.services.get_user_by_email") as mock_get_user:
        mock_get_user.return_value = user
        with patch("npo.modules.auth.services.verify_password") as mock_verify:
            mock_verify.return_value = True
            out = await authenticate_user(override_db_session, sub, password)

    assert out == user


@pytest.mark.asyncio
async def test_get_current_user_no_username(override_db_session):
    """
    Test that get_current_user raises an exception if the token does not contain a 'sub' (username).
    """
    token = "fake_token_string"

    with patch("npo.modules.auth.services.decode_access_token") as mock_decode:
        mock_decode.return_value = {"sub": None}

        with pytest.raises(UnauthorizedUserError) as exc_info:
            await get_current_user(override_db_session, token)

    assert exc_info.value.code == ERROR_UNAUTHORIZED_USER_ERROR


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_error(override_db_session):
    """
    Test that get_current_user raises an exception if the token is invalid.
    """
    token = "fake_token_string"

    with patch("npo.modules.auth.services.decode_access_token") as mock_decode:
        mock_decode.side_effect = InvalidTokenError()

        with pytest.raises(UnauthorizedUserError) as exc_info:
            await get_current_user(override_db_session, token)

    assert exc_info.value.code == ERROR_UNAUTHORIZED_USER_ERROR


@pytest.mark.asyncio
async def test_get_current_user_no_user(override_db_session):
    """
    Test that get_current_user raises an exception if the user is not found.
    """
    token = "fake_token_string"

    with patch("npo.modules.auth.services.decode_access_token") as mock_decode:
        mock_decode.return_value = {"sub": "fake_uid"}
        with patch("npo.modules.auth.services.get_user_by_uid") as mock_get_user:
            mock_get_user.return_value = None
            with pytest.raises(UnauthorizedUserError) as exc_info:
                await get_current_user(override_db_session, token)

    assert exc_info.value.code == ERROR_UNAUTHORIZED_USER_ERROR


@pytest.mark.asyncio
async def test_get_current_user_success(override_db_session):
    """
    Test that get_current_user returns the user if found.
    """
    token = "fake_token_string"

    with patch("npo.modules.auth.services.decode_access_token") as mock_decode:
        mock_decode.return_value = {"sub": "fake_uid"}
        with patch("npo.modules.auth.services.get_user_by_uid") as mock_get_user:
            mock_get_user.return_value = "fake_user"
            user = await get_current_user(override_db_session, token)

    assert user == "fake_user"


@pytest.mark.asyncio
async def test_get_current_active_user_inactive_user(override_db_session):
    """
    Test that get_current_active_user raises an exception if the user is inactive.
    """
    user = MagicMock()
    user.is_active = False
    with pytest.raises(InactiveUserError) as exc_info:
        await get_current_active_user(user)

    assert exc_info.value.code == ERROR_INACTIVE_USER_ERROR


@pytest.mark.asyncio
async def test_get_current_active_user_success(override_db_session):
    """
    Test that get_current_active_user is active.
    """
    user = MagicMock()
    user.is_active = True
    out = await get_current_active_user(user)
    assert out == user


@pytest.mark.asyncio
async def test_get_oauth_user_info_fetch_user_info_error(override_db_session):
    client = MagicMock()
    client.server_metadata = {"userinfo_endpoint": "https://example.com/userinfo"}
    client.userinfo.side_effect = Exception("Failed to fetch user info")
    token = {"access_token": "fake_token"}
    provider = "fake_provider"
    with patch("npo.modules.auth.services.logger") as mock_logger:
        out = await get_oauth_user_info(client, token, provider)

        assert out == {}
        mock_logger.error.assert_called_once()
        assert "Failed to fetch user info" in str(mock_logger.error.call_args)


@pytest.mark.asyncio
async def test_get_oauth_user_info_from_endpoint_void(override_db_session):
    """
    Test that get_oauth_user_info get void user info from the provider's userinfo endpoint.
    """
    client = AsyncMock()
    client.server_metadata = {"userinfo_endpoint": "https://example.com/userinfo"}
    client.userinfo.return_value = {}
    token = {"access_token": "fake_token"}
    provider = "fake_provider"
    out = await get_oauth_user_info(client, token, provider)
    assert out == {}


@pytest.mark.asyncio
async def test_get_oauth_user_info_from_endpoint_without_sub_or_id(override_db_session):
    """
    Test that get_oauth_user_info from the provider's userinfo endpoint without sub or id.
    """
    client = AsyncMock()
    client.server_metadata = {"userinfo_endpoint": "https://example.com/userinfo"}
    client.userinfo.return_value = client.userinfo.return_value = {
        "email": "fake_email",
        "email_verified": True,
    }
    token = {"access_token": "fake_token"}
    provider = "fake_provider"
    with patch("npo.modules.auth.services.get_email_from_provider") as mock_get_email:
        mock_get_email.return_value = ("fake_email", True)
        out = await get_oauth_user_info(client, token, provider)
    assert out == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_user_info", "expected_sub"),
    [
        (
            {
                "sub": "fake_sub",
                "email": "fake_email",
                "email_verified": True,
                "picture": "http://example.com/avatar.png",
                "given_name": "Fake",
                "family_name": "User",
                "name": "Fake User",
            },
            "fake_sub",
        ),
        (
            {
                "id": "fake_id_123",
                "email": "fake_email",
                "email_verified": True,
                "picture": "http://example.com/avatar.png",
                "given_name": "Fake",
                "family_name": "User",
                "name": "Fake User",
            },
            "fake_id_123",
        ),
    ],
)
async def test_get_oauth_user_info_from_endpoint_success(
    override_db_session, provider_user_info, expected_sub
):
    """
    Test that get_oauth_user_info successfully fetches and normalizes user info from the
    provider's userinfo endpoint, handling both 'sub' and 'id' as identifiers.
    """
    client = AsyncMock()
    client.server_metadata = {"userinfo_endpoint": "https://example.com/userinfo"}
    client.userinfo.return_value = provider_user_info
    token = {"access_token": "fake_token"}
    provider = "fake_provider"
    with patch("npo.modules.auth.services.get_email_from_provider") as mock_get_email:
        mock_get_email.return_value = ("fake_email", True)
        out = await get_oauth_user_info(client, token, provider)

    # Check that all expected keys are present in the output dictionary
    expected_keys = [
        "email",
        "email_verified",
        "sub",
        "picture_url",
        "given_name",
        "family_name",
        "name",
    ]
    assert all(key in out for key in expected_keys)

    # Check the values of the normalized data
    assert out["email"] == "fake_email"
    assert out["email_verified"] is True
    assert out["sub"] == expected_sub
    assert out["picture_url"] == "http://example.com/avatar.png"
    assert out["given_name"] == "Fake"
    assert out["family_name"] == "User"
    assert out["name"] == "Fake User"


@pytest.mark.asyncio
async def test_get_email_from_provider_success():
    client = AsyncMock()
    token = "fake_token"
    user_info = {
        "email": "fake_email",
        "email_verified": True,
    }
    provider = "fake_provider"

    email, email_verified = await get_email_from_provider(client, token, provider, user_info)
    assert email == "fake_email"
    assert email_verified is True


@pytest.mark.asyncio
async def test_get_email_from_github_provider_success_with_email():
    client = AsyncMock()
    token = "fake_token"
    user_info = {
        "email": "fake_email",
    }
    provider = "github"

    email, email_verified = await get_email_from_provider(client, token, provider, user_info)
    assert email == "fake_email"
    assert email_verified is True


@pytest.mark.asyncio
async def test_get_email_from_github_provider_success_without_email():
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = [{"primary": True, "verified": True, "email": "fake_email"}]
    client.get.return_value = response
    token = "fake_token"
    user_info = {}
    provider = "github"

    email, email_verified = await get_email_from_provider(client, token, provider, user_info)
    assert email == "fake_email"
    assert email_verified is True


@pytest.mark.asyncio
async def test_get_email_from_github_provider_failed_without_email():
    client = AsyncMock()
    client.get.side_effect = Exception("Github exception")
    token = {"access_token": "fake_token"}
    user_info = {}
    provider = "github"
    with patch("npo.modules.auth.services.logger") as mock_logger:
        out = await get_email_from_provider(client, token, provider, user_info)

        assert out == (None, None)
        mock_logger.warning.assert_called_once()
        assert "Failed to fetch emails from GitHub" in str(mock_logger.warning.call_args)


@pytest.mark.parametrize(
    ("user"),
    [
        ({"given_name": "John", "family_name": "Doe"}),
        ({"name": "John Doe"}),
    ],
)
def test_extract_name_parts_success(user):
    firstname, lastname = extract_name_parts(user)
    assert firstname == "John"
    assert lastname == "Doe"
