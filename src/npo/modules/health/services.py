import logging
import os
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core import config
from npo.core.database import get_session

logger = logging.getLogger(__name__)


async def check_database(session: Annotated[AsyncSession, Depends(get_session)]) -> bool:
    try:
        await session.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        logger.exception("Database connection error")
        return False


async def check_upload_directory() -> bool:
    return os.path.exists(config.settings.uploads_dir)


async def check_storage_directory() -> bool:
    return os.path.exists(config.settings.storage_dir)
