import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core.security import verify_password
from npo.modules.users import crud
from npo.modules.users.models import User
from npo.modules.users.schema import UserCreate, UserUpdate

pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def test_user(override_db_session) -> User:
    """Fixture to create a test user in the database.

    This fixture assumes that a `db_session` fixture is available,
    which is common in FastAPI/SQLAlchemy projects.
    """
    user_in = UserCreate(
        email="test@example.com",
        password="123_Strong|password",
        firstname="Test",
        lastname="User",
    )
    return await crud.create_user(db=override_db_session, user_in=user_in)


class TestUserCrud:
    async def test_create_user_ok(self, override_db_session: AsyncSession):
        """Tests the successful creation of a user."""
        user_in = UserCreate(
            email="newuser@example.com",
            password="123_Strong|password",
            firstname="New",
            lastname="User",
        )
        db_user = await crud.create_user(db=override_db_session, user_in=user_in)

        assert db_user.email == user_in.email
        assert db_user.firstname == user_in.firstname
        assert db_user.is_superadmin is False
        assert db_user.uid is not None
        assert verify_password(user_in.password, db_user.password)

        # Verify that the user is in the database
        retrieved_user = await crud.get_user_by_email(db=override_db_session, email=user_in.email)
        assert retrieved_user is not None
        assert retrieved_user.uid == db_user.uid

    async def test_create_user_duplicate_email(
        self, override_db_session: AsyncSession, test_user: User
    ):
        """Tests that creating a user with a duplicate email fails."""
        user_in = UserCreate(
            email=test_user.email,  # Same email as test_user
            password="123_Strong|password",
        )
        with pytest.raises(IntegrityError):
            await crud.create_user(db=override_db_session, user_in=user_in)

    async def test_get_users_empty(self, override_db_session: AsyncSession):
        """Tests fetching users from an empty database."""
        users = await crud.get_users(db=override_db_session)
        assert users == []

    async def test_get_users_with_pagination(self, override_db_session: AsyncSession):
        """Tests fetching users with pagination."""
        # Create 3 users
        created_users = []
        for i in range(3):
            user_in = UserCreate(email=f"user{i}@example.com", password="123_Strong|password")
            user = await crud.create_user(db=override_db_session, user_in=user_in)
            created_users.append(user)

        # Sort created users by uid to match the query order
        created_users.sort(key=lambda u: u.uid)

        # Fetch the first 2
        users_page1 = await crud.get_users(db=override_db_session, skip=0, limit=2)
        expected_users_number = 2
        assert len(users_page1) == expected_users_number
        assert users_page1[0].uid == created_users[0].uid
        assert users_page1[1].uid == created_users[1].uid

        # Fetch the last one
        users_page2 = await crud.get_users(db=override_db_session, skip=2, limit=2)
        assert len(users_page2) == 1
        assert users_page2[0].uid == created_users[2].uid

    async def test_update_user_fields(self, override_db_session: AsyncSession, test_user: User):
        """Tests updating a user's attributes."""
        original_email = test_user.email
        update_data = UserUpdate(firstname="Updated", lastname="Name")

        updated_user = await crud.update_user(
            db=override_db_session, db_user=test_user, user_in=update_data
        )

        assert updated_user.firstname == "Updated"
        assert updated_user.lastname == "Name"
        assert updated_user.email == original_email  # The email should not have changed

    async def test_update_user_password(self, override_db_session: AsyncSession, test_user: User):
        """Tests updating a user's password."""
        old_password_hash = test_user.password
        new_password = "new_123_Strong|password"
        update_data = UserUpdate(password=new_password)

        updated_user = await crud.update_user(
            db=override_db_session, db_user=test_user, user_in=update_data
        )

        assert updated_user.password is not None
        assert updated_user.password != old_password_hash
        assert verify_password(new_password, updated_user.password)
        # The old password should no longer be valid
        assert not verify_password("123_Strong|password", updated_user.password)
