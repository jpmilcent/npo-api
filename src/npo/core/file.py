from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from npo.models.file import File as FileStorage


async def get_file_by_file_hash(file_hash: str, db: AsyncSession) -> FileStorage | None:
    stmt = select(FileStorage).filter(FileStorage.hash.ilike(f"{file_hash}%"))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_file_by_pixel_hash(pixel_hash: str, db: AsyncSession) -> FileStorage | None:
    stmt = select(FileStorage).filter(FileStorage.pixel_hash.ilike(f"{pixel_hash}%"))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_file_by_perceptual_hash(perceptual_hash: str, db: AsyncSession) -> FileStorage | None:
    stmt = select(FileStorage).filter(FileStorage.perceptual_hash.ilike(f"{perceptual_hash}%"))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_file_by_image_unique_id(image_unique_id: str, db: AsyncSession) -> FileStorage | None:
    stmt = select(FileStorage).filter_by(image_unique_id=image_unique_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
