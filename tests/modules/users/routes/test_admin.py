import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.main import app
from npo.modules.users import crud
from npo.modules.users.models import User
from npo.modules.users.schema import UserCreate

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def normal_user_client(override_db_session):
    """Provides an authenticated client for a normal user (non-superadmin)."""
    user_in = UserCreate(
        email="normal@example.com",
        password="Pass|word123",
        is_superadmin=False,
    )
    await crud.create_user(db=override_db_session, user_in=user_in)

    app.dependency_overrides[get_session] = lambda: override_db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/auth/login",
            data={"username": user_in.email, "password": user_in.password},
        )
        assert response.status_code == status.HTTP_200_OK
        token = response.json()["access_token"]
        ac.headers.update({"Authorization": f"Bearer {token}"})
        yield ac
    app.dependency_overrides.clear()


class TestUserAdminRoutes:
    """Tests for user administration routes, assuming super-administrator access.

    The `client` fixture is authenticated as a super-administrator.
    """

    async def test_read_users_ok(self, client: AsyncClient, test_user: User):
        response = await client.get("/users/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["sub"] == test_user.uid
        assert data[0]["email"] == test_user.email

    async def test_read_users_pagination(self, client: AsyncClient, override_db_session):
        # The main test user already exists. Let's create 2 more.
        for i in range(2):
            user_in = UserCreate(email=f"user{i}@example.com", password="Pass|word123")
            await crud.create_user(db=override_db_session, user_in=user_in)

        # Fetch the first 2 users
        expected_users_number = 2
        response = await client.get("/users/?limit=2")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == expected_users_number

        # Fetch the last one
        expected_users_number = 1
        response = await client.get("/users/?skip=2&limit=2")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == expected_users_number

    async def test_create_user_ok(self, client: AsyncClient):
        new_user_data = {
            "email": "newadminuser@example.com",
            "password": "new_|Password_123",
            "firstname": "New",
            "lastname": "Admin",
            "is_superadmin": True,
        }
        response = await client.post("/users/", json=new_user_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == new_user_data["email"]
        assert data["firstname"] == new_user_data["firstname"]
        assert data["is_superadmin"] is True
        assert "sub" in data

    async def test_create_user_duplicate_email(self, client: AsyncClient, test_user: User):
        response = await client.post(
            "/users/", json={"email": test_user.email, "password": "Pass|word123"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["detail"]
        assert error["code"] == ErrorCode.EMAIL_ALREADY_REGISTERED

    async def test_read_user_by_uid_ok(self, client: AsyncClient, test_user: User):
        response = await client.get(f"/users/{test_user.uid}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["sub"] == test_user.uid
        assert data["email"] == test_user.email

    async def test_read_user_by_uid_not_found(self, client: AsyncClient):
        response = await client.get(f"/users/{uuid.uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()["detail"]
        assert error["code"] == ErrorCode.USER_NOT_FOUND

    async def test_update_user_by_id_ok(self, client: AsyncClient, override_db_session):
        user_in = UserCreate(email="to_update@example.com", password="Pass|word123")
        user = await crud.create_user(db=override_db_session, user_in=user_in)

        update_data = {"firstname": "UpdatedFirstname", "is_active": False}
        response = await client.patch(f"/users/{user.uid}", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["firstname"] == "UpdatedFirstname"
        assert data["is_active"] is False

    async def test_update_user_by_id_not_found(self, client: AsyncClient):
        response = await client.patch(f"/users/{uuid.uuid4()}", json={"firstname": "test"})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()["detail"]
        assert error["code"] == ErrorCode.USER_NOT_FOUND

    async def test_delete_user_by_id_ok(self, client: AsyncClient, override_db_session):
        user_in = UserCreate(email="to_delete@example.com", password="Pass|word123")
        user = await crud.create_user(db=override_db_session, user_in=user_in)

        response = await client.delete(f"/users/{user.uid}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_response = await client.get(f"/users/{user.uid}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_user_by_id_not_found(self, client: AsyncClient):
        response = await client.delete(f"/users/{uuid.uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        error = response.json()["detail"]
        assert error["code"] == ErrorCode.USER_NOT_FOUND


class TestUserAdminPermissions:
    """Verifies that non-superadmin users cannot access admin routes."""

    @pytest.mark.parametrize(
        ("method", "path", "data"),
        [
            ("GET", "/users/", None),
            ("POST", "/users/", {"email": "a@b.com", "password": "Pass|word123"}),
            ("GET", "/users/00000000-0000-0000-0000-000000000000", None),
            ("PATCH", "/users/00000000-0000-0000-0000-000000000000", {"firstname": "test"}),
            ("DELETE", "/users/00000000-0000-0000-0000-000000000000", None),
        ],
    )
    async def test_admin_routes_forbidden_for_normal_user(
        self, normal_user_client: AsyncClient, method: str, path: str, data: dict | None
    ):
        kwargs = {"json": data} if data else {}
        response = await normal_user_client.request(method, path, **kwargs)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        error = response.json()["detail"]
        assert error["code"] == ErrorCode.UNAUTHORIZED_USER_ERROR
        assert error["message"] == "User is not a superadmin"
