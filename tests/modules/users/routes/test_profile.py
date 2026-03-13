from datetime import timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.security import create_access_token, verify_password
from npo.main import app
from npo.modules.users import crud
from npo.modules.users.models import User
from npo.modules.users.schema import UserCreate

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def oauth_only_user_client(override_db_session: AsyncSession):
    """Provides an authenticated client for a user with only an OAuth provider (no password)."""
    user_in = UserCreate(email="oauth@example.com", password="Pass|word123")
    user = await crud.create_user(db=override_db_session, user_in=user_in)
    user.password = None  # Simulate an OAuth-only user
    user.oauth_providers = {"google": {"sub": "123456789", "email": "oauth@example.com"}}
    await override_db_session.commit()
    await override_db_session.refresh(user)

    app.dependency_overrides[get_session] = lambda: override_db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Manually create a token because there is no password to log in
        token = create_access_token(data={"sub": user.uid})
        ac.headers.update({"Authorization": f"Bearer {token}"})
        yield ac, user
    app.dependency_overrides.clear()


class TestUserProfileRoutes:
    """Tests for user profile routes (/users/me)."""

    async def test_read_me_ok(self, client: AsyncClient, test_user: User):
        """Tests fetching the current user's profile."""
        response = await client.get("/users/me")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["sub"] == test_user.uid
        assert data["email"] == test_user.email

    async def test_update_profile_ok(
        self, client: AsyncClient, test_user: User, override_db_session: AsyncSession
    ):
        """Tests updating the user's first and last name."""
        update_data = {"firstname": "UpdatedFirst", "lastname": "UpdatedLast"}
        response = await client.patch("/users/me", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["firstname"] == "UpdatedFirst"
        assert data["lastname"] == "UpdatedLast"
        assert data["full_name"] == "UpdatedFirst UpdatedLast"
        assert data["email"] == test_user.email  # The email should not change

        await override_db_session.refresh(test_user)
        assert test_user.firstname == "UpdatedFirst"

    @patch("npo.modules.users.routes.profile.send_verification_email")
    async def test_update_profile_email_change(
        self,
        mock_send_email,
        client: AsyncClient,
        test_user: User,
        override_db_session: AsyncSession,
    ):
        """Tests that changing the email triggers verification."""
        new_email = "new.email@example.com"
        test_user.email_verified = True
        await override_db_session.commit()

        response = await client.patch("/users/me", json={"email": new_email})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == new_email
        assert data["email_verified"] is False

        # Verify that the background task was called
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args[0]
        assert call_args[0] == new_email
        assert isinstance(call_args[1], str)  # The token

        await override_db_session.refresh(test_user)
        assert test_user.email == new_email
        assert test_user.email_verified is False

    async def test_update_profile_duplicate_email(
        self, client: AsyncClient, override_db_session: AsyncSession
    ):
        """Tests that updating to an existing email fails."""
        other_user_in = UserCreate(email="other@example.com", password="Pass|word123")
        await crud.create_user(db=override_db_session, user_in=other_user_in)

        response = await client.patch("/users/me", json={"email": "other@example.com"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["detail"]
        assert error["code"] == ErrorCode.EMAIL_ALREADY_REGISTERED

    async def test_update_password_ok(
        self,
        client: AsyncClient,
        test_user: User,
        test_user_data: dict,
        override_db_session: AsyncSession,
    ):
        """Tests the successful update of the user's password."""
        new_password = "new_Strong|Password1"
        update_data = {
            "old_password": test_user_data["password"],
            "new_password": new_password,
        }
        response = await client.put("/users/me/password", json=update_data)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        await override_db_session.refresh(test_user)
        assert verify_password(new_password, test_user.password)
        assert not verify_password(test_user_data["password"], test_user.password)

    async def test_update_password_incorrect_old(self, client: AsyncClient):
        """Tests that updating the password with an incorrect old password fails."""
        update_data = {"old_password": "wrong|123Password", "new_password": "new|123Password"}
        response = await client.put("/users/me/password", json=update_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["detail"]
        assert error["code"] == ErrorCode.INCORRECT_PASSWORD

    async def test_delete_me_ok(self, client: AsyncClient, test_user: User):
        """Tests that a user can delete their own account."""
        uid = test_user.uid
        response = await client.delete("/users/me")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify that the user is gone. To do this, we try to access an
        # admin route. The call should fail with an authorization error
        # because the client's token corresponds to a user that no longer exists.
        # The original assertion (404) was incorrect because security comes first.
        get_response = await client.get(f"/users/{uid}")
        assert get_response.status_code == status.HTTP_403_FORBIDDEN
        error = get_response.json()["detail"]
        assert error["code"] == ErrorCode.UNAUTHORIZED_USER_ERROR

    async def test_read_providers(
        self, client: AsyncClient, test_user: User, override_db_session: AsyncSession
    ):
        """Tests fetching authentication providers for a user."""
        # 1. User with only a password
        response = await client.get("/users/me/providers")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == ["local"]

        # 2. Add an OAuth provider
        test_user.oauth_providers = {"google": {"sub": "123"}}
        await override_db_session.commit()

        response = await client.get("/users/me/providers")
        assert response.status_code == status.HTTP_200_OK
        assert sorted(response.json()) == ["google", "local"]

    async def test_delete_provider_ok(
        self, client: AsyncClient, test_user: User, override_db_session: AsyncSession
    ):
        """Tests deleting an OAuth provider when other authentication methods exist."""
        test_user.oauth_providers = {"google": {"sub": "123"}}
        await override_db_session.commit()

        response = await client.delete("/users/me/providers/google")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        await override_db_session.refresh(test_user)
        assert not test_user.oauth_providers

    async def test_delete_last_provider_ko(self, oauth_only_user_client):
        """Tests that deleting the last authentication method fails."""
        client, user = oauth_only_user_client
        provider_name = next(iter(user.oauth_providers.keys()))

        response = await client.delete(f"/users/me/providers/{provider_name}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["detail"]
        assert error["code"] == ErrorCode.CANNOT_REMOVE_LAST_AUTH_METHOD

    async def test_delete_nonexistent_provider(self, client: AsyncClient):
        """Tests that deleting an unlinked provider fails."""
        response = await client.delete("/users/me/providers/facebook")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()["detail"]
        assert error["code"] == ErrorCode.PROVIDER_NOT_FOUND

    async def test_verify_email_ok(
        self, client: AsyncClient, test_user: User, override_db_session: AsyncSession
    ):
        """Tests successful email verification with a valid token."""
        test_user.email_verified = False
        await override_db_session.commit()

        token = create_access_token(
            data={"sub": test_user.email, "type": "email_verification"},
            expires_delta=timedelta(hours=1),
        )
        response = await client.get(f"/users/verify-email?token={token}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "Email successfully verified"}

        await override_db_session.refresh(test_user)
        assert test_user.email_verified is True

    async def test_verify_email_invalid_token(self, client: AsyncClient):
        """Tests that email verification fails with an invalid token."""
        response = await client.get("/users/verify-email?token=invalid-token")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["detail"]
        assert error["code"] == ErrorCode.INVALID_VERIFICATION_TOKEN

    async def test_verify_email_wrong_type_token(self, client: AsyncClient):
        """
        Tests that email verification fails with a token of the wrong type
        (e.g., an access token).
        """
        token = client.headers["Authorization"].split(" ")[1]
        response = await client.get(f"/users/verify-email?token={token}")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["detail"]
        assert error["code"] == ErrorCode.INVALID_VERIFICATION_TOKEN
