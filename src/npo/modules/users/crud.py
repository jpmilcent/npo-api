from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core.security import get_password_hash
from npo.modules.users.models import User
from npo.modules.users.schema import UserCreate, UserUpdate


async def get_user_by_oauth(db: AsyncSession, provider: str, sub: str) -> User | None:
    stmt = select(User).where(User.oauth_providers[provider]["sub"].as_string() == sub)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).filter_by(email=email)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_uid(db: AsyncSession, uid: str) -> User | None:
    stmt = select(User).filter_by(uid=uid)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[User]:
    stmt = select(User).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    db_user = User(
        email=user_in.email,
        password=get_password_hash(user_in.password),
        firstname=user_in.firstname,
        lastname=user_in.lastname,
        is_active=user_in.is_active,
        is_superadmin=user_in.is_superadmin,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def update_user(db: AsyncSession, db_user: User, user_in: UserUpdate) -> User:
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data:
        password = update_data.pop("password")
        db_user.password = get_password_hash(password)

    for field, value in update_data.items():
        setattr(db_user, field, value)

    await db.commit()
    await db.refresh(db_user)
    return db_user
