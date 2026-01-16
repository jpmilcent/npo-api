from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from npo.files.models import File as FileStorage


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


async def get_file_by_image_unique_id(
    image_unique_id: str | None, db: AsyncSession
) -> FileStorage | None:
    file = None
    if image_unique_id is not None:
        stmt = select(FileStorage).filter_by(image_unique_id=image_unique_id)
        result = await db.execute(stmt)
        file = result.scalar_one_or_none()
    return file


async def get_files_list(db: AsyncSession, skip: int = 0, limit: int = 100):
    stmt_count = select(func.count()).select_from(FileStorage)
    total = await db.scalar(stmt_count)

    stmt = (
        select(
            FileStorage.id,
            FileStorage.pixel_hash.label("hash"),
            FileStorage.name,
            FileStorage.mime,
            FileStorage.size,
            FileStorage.datetime_shooting,
            FileStorage.latitude,
            FileStorage.longitude,
            FileStorage.created_at,
            FileStorage.updated_at,
        )
        .order_by(FileStorage.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.mappings().all(), total
