import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from npo.core.database import get_session
from npo.main import app


@pytest_asyncio.fixture(loop_scope="session")
async def client(override_db_session, test_user_data: dict, override_settings, test_user):
    """
    Fixture providing a real async HTTP client.
    Overrides the application's database dependency.
    """
    # Override the get_session dependency to use the test session
    app.dependency_overrides[get_session] = lambda: override_db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Log in to get the token
        login_data = {
            "username": test_user_data["email"],
            "password": test_user_data["password"],
        }
        response = await ac.post("/auth/login", data=login_data)
        assert response.status_code == status.HTTP_200_OK, "Failed to log in test user"
        token_data = response.json()
        access_token = token_data["access_token"]

        # Set the token for all subsequent requests
        ac.headers.update({"Authorization": f"Bearer {access_token}"})

        yield ac

    # Clear dependency overrides after the test
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def session_client(db_engine, override_settings):
    """
    Fixture providing a client that commits changes (for seeding data).
    """
    # Create a session maker that commits (unlike the test one that rolls back)
    SessionLocal = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async def get_session_override():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
