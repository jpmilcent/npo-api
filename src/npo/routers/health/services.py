import os

from fastapi import Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import text

from npo import config
from npo.database import get_session


async def check_database(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as e:
        print(e)
        return False


async def check_upload_directory():
    return os.path.exists(config.settings.uploads_dir)


async def check_storage_directory():
    return os.path.exists(config.settings.storage_dir)
