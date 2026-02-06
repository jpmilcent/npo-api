import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from npo.common.decorators import NpoApiRoute
from npo.common.pagination import create_paginated_response
from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.exceptions import APIException
from npo.core.i18n import _
from npo.modules.images.crud import get_image_by_pixel_hash, get_images_list
from npo.modules.images.exceptions import (
    DomainError,
    DuplicateImageError,
    FileTooLargeError,
    ImageDecodingError,
    ImageProcessingError,
    InsufficientStorageError,
    StorageError,
    UnsupportedGpsDatumError,
)
from npo.modules.images.metadata_formatters import MetadataFormatter
from npo.modules.images.schemas import Image, ImageListResponse, PhotographyMetadata
from npo.modules.images.services import (
    build_image_infos,
    check_duplicates_by_image_unique_id,
    check_duplicates_by_perceptual_hash,
    compute_hash,
    compute_hash_pathes,
    compute_perceptual_hash,
    compute_pixel_hash,
    create_dzi,
    extract_metadata,
    get_image,
    get_tile_from_dzi,
    is_web_format,
    move_file,
    save_file,
    store_image_infos,
)

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
    page: Annotated[int, Query(description=_("Page number for pagination."), ge=1)] = 1,
    size: Annotated[int, Query(description=_("Number of items per page."), ge=1, le=200)] = 100,
) -> dict:
    skip = (page - 1) * size
    limit = size
    images, total = await get_images_list(db, skip=skip, limit=limit)
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
    # TODO: create a schema for this type of response
    response_model=dict[str, Image],
)
async def compute_upload_images(
    files: Annotated[
        list[UploadFile],
        File(description=_("List of image files to upload.")),
    ],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    infos = {}
    # Process each received image files
    for upload_file in files:
        file = await build_image_infos(upload_file)

        try:
            await save_file(upload_file, file)
            await compute_perceptual_hash(file)
            await check_duplicates_by_perceptual_hash(file, db)
            await extract_metadata(file)
            await check_duplicates_by_image_unique_id(file, db)

            await compute_hash(file)
            await compute_pixel_hash(file)
            await compute_hash_pathes(file)
            await move_file(file)
            await store_image_infos(file, db)
            await create_dzi(file)
        except DomainError as e:
            status_code = DOMAIN_ERROR_STATUS_MAP.get(type(e), status.HTTP_400_BAD_REQUEST)
            raise APIException(
                status_code=status_code,
                code=e.code,
                message=e.code.formatMsg(**e.kwargs),
            ) from e

        logger.info("File {file.name} was uploaded successfully!")
        infos[file.name] = file.__dict__
    return infos


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
    pixel_hash: Annotated[str, Path(description=_("Image pixel hash"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    file = await get_image_by_pixel_hash(pixel_hash, db)
    if file:
        image_bytes: bytes | None = await get_image(file)
        if image_bytes is None:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.IMAGE_NOT_FOUND,
                message=ErrorCode.IMAGE_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
            )
        media_type = file.mime if is_web_format(file) else "image/jpeg"
        return Response(content=image_bytes, media_type=media_type)
    else:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.IMAGE_NOT_FOUND,
            message=ErrorCode.IMAGE_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
        )


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
    pixel_hash: Annotated[str, Path(description=_("Image pixel hash"))],
    zoom: Annotated[int, Path(description=_("Zoom level"))],
    x: Annotated[int, Path(description=_("X coordinate"))],
    y: Annotated[int, Path(description=_("Y coordinate"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    file_storage = await get_image_by_pixel_hash(pixel_hash, db)
    if file_storage:
        image_bytes: bytes | None = await get_tile_from_dzi(file_storage, zoom, x, y)
        if image_bytes is None:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=ErrorCode.IMAGE_DZI_NOT_FOUND,
                message=ErrorCode.IMAGE_DZI_NOT_FOUND.formatMsg(
                    pixel_hash=pixel_hash, zoom=zoom, x=x, y=y
                ),
            )
        return Response(content=image_bytes, media_type="image/jpeg")
    else:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.IMAGE_NOT_FOUND,
            message=ErrorCode.IMAGE_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
        )


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
    pixel_hash: Annotated[str, Path(description=_("Image pixel hash"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    file_storage = await get_image_by_pixel_hash(pixel_hash, db)
    if file_storage:
        return file_storage.meta_data
    else:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.RAW_METADATA_NOT_FOUND,
            message=ErrorCode.RAW_METADATA_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
        )


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
    pixel_hash: Annotated[str, Path(description=_("Image pixel hash"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    file_storage = await get_image_by_pixel_hash(pixel_hash, db)
    meta = file_storage.meta_data if file_storage else None
    if meta:
        return {
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
    else:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.PHOTOGRAPHY_METADATA_NOT_FOUND,
            message=ErrorCode.PHOTOGRAPHY_METADATA_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
        )


@images_router.get("/{path:path}", include_in_schema=False)
async def images_catch_all(path: str):
    raise APIException(
        status_code=status.HTTP_404_NOT_FOUND,
        code=ErrorCode.IMAGES_WEBSERVICE_NOT_FOUND,
        message=ErrorCode.IMAGES_WEBSERVICE_NOT_FOUND.formatMsg(path=path),
    )
