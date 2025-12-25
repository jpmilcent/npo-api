from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from npo.models.file import File as FileStorage


async def get_file_by_hash(file_hash: str, db: AsyncSession) -> FileStorage | None:
    stmt = select(FileStorage).filter_by(hash=file_hash)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
