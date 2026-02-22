import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from npo.common.decorators import NpoApiRoute
from npo.common.pagination import create_paginated_response
from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.exceptions import APIException, DomainError
from npo.core.i18n import _
from npo.modules.auth.services import get_current_active_user
from npo.modules.images.crud import get_images_list
from npo.modules.images.dependencies import (
    get_image_for_raw_metadata,
    get_image_for_raw_metadata_photography,
    get_image_for_user,
)
from npo.modules.images.exceptions import (
    DuplicateImageError,
    FileTooLargeError,
    ImageDecodingError,
    ImageProcessingError,
    InsufficientStorageError,
    StorageError,
    UnsupportedGpsDatumError,
)
from npo.modules.images.metadata_formatters import MetadataFormatter
from npo.modules.images.models import Image
from npo.modules.images.schemas import (
    ImageListResponse,
    PhotographyMetadata,
    UploadResponse,
)
from npo.modules.images.services import ImageService
from npo.modules.users.models import User

logger = logging.getLogger(__name__)

IMAGE_NOT_FOUND_RESPONSE = {
    "description": _("Image not found"),
    "code": ErrorCode.IMAGE_NOT_FOUND,
    "message": ErrorCode.IMAGE_NOT_FOUND.message,
}

RAW_METADATA_NOT_FOUND_RESPONSE = {
    "description": _("Raw metadata not found"),
    "code": ErrorCode.RAW_METADATA_NOT_FOUND,
    "message": ErrorCode.RAW_METADATA_NOT_FOUND.message,
}

PHOTOGRAPHY_METADATA_NOT_FOUND_RESPONSE = {
    "description": _("Photography metadata not found"),
    "code": ErrorCode.PHOTOGRAPHY_METADATA_NOT_FOUND,
    "message": ErrorCode.PHOTOGRAPHY_METADATA_NOT_FOUND.message,
}

DOMAIN_ERROR_STATUS_MAP = {
    DuplicateImageError: status.HTTP_409_CONFLICT,
    InsufficientStorageError: status.HTTP_507_INSUFFICIENT_STORAGE,
    FileTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
    StorageError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ImageDecodingError: status.HTTP_400_BAD_REQUEST,
    ImageProcessingError: status.HTTP_400_BAD_REQUEST,
    UnsupportedGpsDatumError: status.HTTP_400_BAD_REQUEST,
}

images_router = APIRouter(
    prefix="/images",
    tags=["Images"],
)
images_route = NpoApiRoute(images_router)


@images_router.get(
    "/",
    summary=_("Get images list"),
    description=_(
        "Retrieves the list of stored images with pagination. "
        "Returns basic metadata (hash, name, date, location)."
    ),
    response_description=_("List of images and pagination information"),
    response_model=ImageListResponse,
)
async def root(
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: Annotated[int, Query(description=_("Page number for pagination."), ge=1)] = 1,
    size: Annotated[int, Query(description=_("Number of items per page."), ge=1, le=200)] = 100,
    user_id: Annotated[
        int | None,
        Query(description=_("Filter by user ID. If not provided, admins see all images.")),
    ] = None,
) -> dict:
    skip = (page - 1) * size
    limit = size
    target_user_id = user_id if current_user.is_superadmin else current_user.id
    images, total = await get_images_list(db, skip=skip, limit=limit, user_id=target_user_id)
    return create_paginated_response(data=images, total=total, page=page, size=limit)


@images_router.post(
    "/upload",
    summary=_("Upload image files"),
    description=_(
        "Upload one or more images. "
        "The system automatically calculates hashes, extracts EXIF metadata, and "
        "generates tiles for Deep Zoom."
    ),
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": _(
                "Images uploaded successfully. "
                "Dictionary of processed files with their information."
            )
        },
        409: {
            "description": _("Duplicate image (perceptual hash or unique ID already exists)"),
            "content": {"application/json": {"example": {"detail": "Duplicate image detected."}}},
        },
        413: {
            "description": _("File too large"),
            "content": {
                "application/json": {
                    "example": {"detail": "File size exceeds the maximum allowed limit."}
                }
            },
        },
        507: {
            "description": _("Insufficient storage space"),
            "content": {
                "application/json": {
                    "example": {"detail": "Not enough disk space to save the file."}
                }
            },
        },
        400: {
            "description": _("Image decoding or processing error"),
            "content": {
                "application/json": {"example": {"detail": "Unable to decode image file."}}
            },
        },
    },
    response_model=UploadResponse,
)
async def compute_upload_images(
    files: Annotated[
        list[UploadFile],
        File(description=_("List of image files to upload.")),
    ],
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UploadResponse:
    infos = {}
    image_service = ImageService(db)
    # Process each received image files
    for upload_file in files:
        try:
            file = await image_service.process_upload(upload_file, current_user)
            infos[file.name] = file
        except DomainError as e:
            status_code = DOMAIN_ERROR_STATUS_MAP.get(type(e), status.HTTP_400_BAD_REQUEST)
            raise APIException(
                status_code=status_code,
                code=e.code,
                message=e.code.formatMsg(**e.kwargs),
            ) from e

    return UploadResponse(root=infos)


@images_router.delete(
    "/{pixel_hash}",
    summary=_("Delete image"),
    description=_("Deletes an image and its associated files using pixel hash."),
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: IMAGE_NOT_FOUND_RESPONSE,
        403: {"description": _("Forbidden")},
    },
)
async def delete_image(
    file_storage: Annotated[Image, Depends(get_image_for_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await db.delete(file_storage)
    await db.commit()


@images_route(
    "/{pixel_hash}",
    summary=_("Get file image"),
    description=_("Retrieves the full original image or its preview using pixel hash."),
    responses={
        200: {
            "content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}},
            "description": _("Image file"),
        },
        404: {"description": _("Image not found")},
    },
    response_class=Response,
    override_404=IMAGE_NOT_FOUND_RESPONSE,
)
async def get_image_full(
    file: Annotated[Image, Depends(get_image_for_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    image_service = ImageService(db)
    image_bytes: bytes | None = await image_service.storage_service.get_image(file)
    if image_bytes is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.IMAGE_NOT_FOUND,
            message=ErrorCode.IMAGE_NOT_FOUND.formatMsg(pixel_hash=file.pixel_hash),
        )
    media_type = file.mime if image_service.storage_service.is_web_format(file) else "image/jpeg"
    return Response(content=image_bytes, media_type=media_type)


@images_route(
    "/{pixel_hash}/{zoom}/{x}/{y}.jpg",
    summary=_("Get tile image"),
    description=_(
        "Retrieves a specific tile (JPEG format) for high-resolution zoom display "
        "using pixel hash, zoom level and coordinates."
    ),
    responses={
        200: {"content": {"image/jpeg": {}}, "description": _("JPEG image tile")},
        404: {"description": _("Image or tile not found")},
    },
    response_class=Response,
    override_404=IMAGE_NOT_FOUND_RESPONSE,
)
async def get_image_tile(
    file_storage: Annotated[Image, Depends(get_image_for_user)],
    zoom: Annotated[int, Path(description=_("Zoom level"))],
    x: Annotated[int, Path(description=_("X coordinate"))],
    y: Annotated[int, Path(description=_("Y coordinate"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    image_service = ImageService(db)
    image_bytes: bytes | None = await image_service.storage_service.get_tile_from_dzi(
        file_storage, zoom, x, y
    )
    if image_bytes is None:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.IMAGE_DZI_NOT_FOUND,
            message=ErrorCode.IMAGE_DZI_NOT_FOUND.formatMsg(
                pixel_hash=file_storage.pixel_hash, zoom=zoom, x=x, y=y
            ),
        )
    return Response(content=image_bytes, media_type="image/jpeg")


@images_route(
    "/{pixel_hash}/metadata",
    summary=_("Get raw metadata"),
    description=_(
        "Returns all raw metadata (EXIF, XMP, etc.) extracted from the file using pixel hash."
    ),
    responses={
        200: {"description": _("Image raw metadata")},
        404: {"description": _("Raw metadata not found")},
    },
    override_404=RAW_METADATA_NOT_FOUND_RESPONSE,
)
async def get_raw_metadata(
    file_storage: Annotated[Image, Depends(get_image_for_raw_metadata)],
):
    return file_storage.meta_data


@images_route(
    "/{pixel_hash}/metadata/photography",
    summary=_("Get photography metadata"),
    description=_(
        "Returns a formatted selection of photography metadata "
        "(ISO, Aperture, Model, etc.) extracted from the file using pixel hash."
    ),
    responses={
        200: {"description": _("Image photography metadata")},
        404: {"description": _("Photography metadata not found")},
    },
    response_model=PhotographyMetadata,
    override_404=PHOTOGRAPHY_METADATA_NOT_FOUND_RESPONSE,
)
async def get_photography_metadata(
    file_storage: Annotated[Image, Depends(get_image_for_raw_metadata_photography)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    meta = file_storage.meta_data
    output = {}
    if meta:
        output = {
            "cameraMaker": meta.get("EXIF:Make"),
            "cameraModel": meta.get("EXIF:Model"),
            "lensModel": meta.get("EXIF:LensModel"),
            "focalLength": MetadataFormatter.format_focal_length(meta.get("EXIF:FocalLength")),
            "focalLengthIn35mmFormat": MetadataFormatter.format_focal_length(
                meta.get("EXIF:FocalLengthIn35mmFormat")
            ),
            "aperture": MetadataFormatter.format_aperture(meta.get("EXIF:FNumber")),
            "shutterSpeed": MetadataFormatter.format_shutter_speed(meta.get("EXIF:ExposureTime")),
            "iso": meta.get("EXIF:ISO") or meta.get("EXIF:ISOSpeedRatings"),
            "flash": MetadataFormatter.format_flash(meta.get("EXIF:Flash")),
            "imageWidth": MetadataFormatter.format_pixels(
                meta.get("File:ImageWidth") or meta.get("EXIF:ExifImageWidth")
            ),
            "imageHeight": MetadataFormatter.format_pixels(
                meta.get("File:ImageHeight") or meta.get("EXIF:ExifImageHeight")
            ),
            "orientation": MetadataFormatter.format_orientation(meta.get("EXIF:Orientation")),
            "whiteBalance": MetadataFormatter.format_white_balance(meta.get("EXIF:WhiteBalance")),
            "exposureProgram": MetadataFormatter.format_exposure_program(
                meta.get("EXIF:ExposureProgram")
            ),
            "exposureMode": MetadataFormatter.format_exposure_mode(meta.get("EXIF:ExposureMode")),
            "exposureCompensation": MetadataFormatter.format_exposure_compensation(
                meta.get("EXIF:ExposureCompensation")
            ),
            "meteringMode": MetadataFormatter.format_metering_mode(meta.get("EXIF:MeteringMode")),
            "sceneCaptureType": MetadataFormatter.format_scene_capture_type(
                meta.get("EXIF:SceneCaptureType")
            ),
            "sceneType": MetadataFormatter.format_scene_type(meta.get("EXIF:SceneType")),
            "colorSpace": MetadataFormatter.format_color_space(meta.get("EXIF:ColorSpace")),
        }
    return output


@images_router.get("/{path:path}", include_in_schema=False)
async def images_catch_all(path: str):
    raise APIException(
        status_code=status.HTTP_404_NOT_FOUND,
        code=ErrorCode.IMAGES_WEBSERVICE_NOT_FOUND,
        message=ErrorCode.IMAGES_WEBSERVICE_NOT_FOUND.formatMsg(path=path),
    )
