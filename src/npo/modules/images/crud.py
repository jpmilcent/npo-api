from collections.abc import Sequence

from sqlalchemy import RowMapping, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from npo.modules.images.models import Image as ImageStorage


async def get_image_by_file_hash(file_hash: str, db: AsyncSession) -> ImageStorage | None:
    stmt = select(ImageStorage).filter(ImageStorage.file_hash.ilike(f"{file_hash}%"))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_image_by_pixel_hash(pixel_hash: str, db: AsyncSession) -> ImageStorage | None:
    stmt = select(ImageStorage).filter(ImageStorage.pixel_hash.ilike(f"{pixel_hash}%"))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_image_by_perceptual_hash(
    perceptual_hash: str, db: AsyncSession
) -> ImageStorage | None:
    stmt = select(ImageStorage).filter(ImageStorage.perceptual_hash.ilike(f"{perceptual_hash}%"))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_image_by_image_unique_id(
    image_unique_id: str | None, db: AsyncSession
) -> ImageStorage | None:
    image = None
    if image_unique_id is not None:
        stmt = select(ImageStorage).filter_by(image_unique_id=image_unique_id)
        result = await db.execute(stmt)
        image = result.scalar_one_or_none()
    return image


async def get_images_list(
    db: AsyncSession, skip: int = 0, limit: int = 100, user_id: int | None = None
) -> tuple[Sequence[RowMapping], int]:
    stmt_count = select(func.count()).select_from(ImageStorage)
    if user_id is not None:
        stmt_count = stmt_count.where(ImageStorage.user_id == user_id)

    total = await db.scalar(stmt_count)
    total = total if total is not None else 0

    stmt = select(
        ImageStorage.id,
        ImageStorage.pixel_hash.label("hash"),
        ImageStorage.name,
        ImageStorage.mime,
        ImageStorage.size,
        ImageStorage.datetime_shooting,
        ImageStorage.latitude,
        ImageStorage.longitude,
        ImageStorage.created_at,
        ImageStorage.updated_at,
    )

    if user_id is not None:
        stmt = stmt.where(ImageStorage.user_id == user_id)

    stmt = (
        stmt.order_by(ImageStorage.created_at.desc(), ImageStorage.id.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.mappings().all(), total
