from typing import Annotated

from fastapi import Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.exceptions import APIException
from npo.modules.auth.services import get_current_active_user
from npo.modules.images.crud import get_image_by_pixel_hash
from npo.modules.images.models import Image
from npo.modules.users.models import User


async def get_image_for_user(
    pixel_hash: Annotated[str, Path(description="Image pixel hash")],
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Image:
    image = await get_image_by_pixel_hash(pixel_hash, db)
    if not image:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.IMAGE_NOT_FOUND,
            message=ErrorCode.IMAGE_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
        )

    if not current_user.is_superadmin and image.user_id != current_user.id:
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code=ErrorCode.FORBIDDEN_IMAGE_ACCESS,
            message=ErrorCode.FORBIDDEN_IMAGE_ACCESS.formatMsg(pixel_hash=pixel_hash),
        )

    return image


async def get_image_for_raw_metadata(
    pixel_hash: Annotated[str, Path(description="Image pixel hash")],
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Image:
    try:
        return await get_image_for_user(pixel_hash, db, current_user)
    except APIException as e:
        if e.status_code == status.HTTP_404_NOT_FOUND:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.RAW_METADATA_NOT_FOUND,
                message=ErrorCode.RAW_METADATA_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
            ) from e
        raise e


async def get_image_for_raw_metadata_photography(
    pixel_hash: Annotated[str, Path(description="Image pixel hash")],
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Image:
    try:
        image = await get_image_for_user(pixel_hash, db, current_user)
    except APIException as e:
        if e.status_code == status.HTTP_404_NOT_FOUND:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.IMAGE_NOT_FOUND,
                message=ErrorCode.IMAGE_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
            ) from e
        raise e

    if not image.meta_data:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.PHOTOGRAPHY_METADATA_NOT_FOUND,
            message=ErrorCode.PHOTOGRAPHY_METADATA_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
        )

    return image
