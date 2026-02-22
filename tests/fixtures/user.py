import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core.security import get_password_hash
from npo.modules.users.models import User


@pytest.fixture(scope="session")
def test_user_data():
    return {"email": "test@example.com", "password": "testpassword"}


@pytest_asyncio.fixture(scope="function")
async def test_user(override_db_session: AsyncSession, test_user_data: dict):
    """
    Fixture to create a test user in the database.
    """
    user = User(
        email=test_user_data["email"],
        password=get_password_hash(test_user_data["password"]),
        is_active=True,
        is_superadmin=True,  # Make user superadmin for full access in tests
    )
    override_db_session.add(user)
    await override_db_session.commit()
    await override_db_session.refresh(user)
    return user
