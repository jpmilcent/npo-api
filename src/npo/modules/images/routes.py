from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from npo.common.decorators import NpoApiRoute
from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.exceptions import APIException
from npo.modules.images.crud import get_image_by_pixel_hash, get_images_list
from npo.modules.images.metadata_formatters import MetadataFormatter
from npo.modules.images.schemas import PhotographyMetadata
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

IMAGE_NOT_FOUND_RESPONSE = {
    "description": "Image not found",
    "code": ErrorCode.IMAGE_NOT_FOUND,
    "message": ErrorCode.IMAGE_NOT_FOUND.message,
}

RAW_METADATA_NOT_FOUND_RESPONSE = {
    "description": "Raw metadata not found",
    "code": ErrorCode.RAW_METADATA_NOT_FOUND,
    "message": ErrorCode.RAW_METADATA_NOT_FOUND.message,
}

PHOTOGRAPHY_METADATA_NOT_FOUND_RESPONSE = {
    "description": "Photography metadata not found",
    "code": ErrorCode.PHOTOGRAPHY_METADATA_NOT_FOUND,
    "message": ErrorCode.PHOTOGRAPHY_METADATA_NOT_FOUND.message,
}

images_router = APIRouter(
    prefix="/images",
    tags=["Images"],
)
images_route = NpoApiRoute(images_router)


@images_router.get(
    "/",
    summary="Get paginated images list",
)
async def root(
    db: Annotated[AsyncSession, Depends(get_session)],
    page: int = 1,
    size: int = 100,
):
    skip = (page - 1) * size
    limit = size
    images, total = await get_images_list(db, skip=skip, limit=limit)
    return {
        "meta": {
            "pagination": {
                "total_items": total,
                "total_pages": (total + limit - 1) // limit,
                "current_page": page,
                "items_per_page": limit,
            }
        },
        "data": images,
    }


@images_router.post(
    "/upload",
    summary="Upload image files",
    status_code=status.HTTP_201_CREATED,
)
async def compute_upload_images(
    files: list[UploadFile], db: Annotated[AsyncSession, Depends(get_session)]
):
    infos = {}
    # Process each received image files
    for upload_file in files:
        file = await build_image_infos(upload_file)

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
        infos[file.name] = file.__dict__

    return infos


@images_route(
    "/{pixel_hash}/{zoom}/{x}/{y}.jpg",
    summary="Get tile image by pixel hash, zoom level and coordinates",
    responses={200: {"content": {"image/jpeg": {}}}},
    response_class=Response,
    override_404=IMAGE_NOT_FOUND_RESPONSE,
)
async def get_image_tile(
    pixel_hash: str, zoom: int, x: int, y: int, db: Annotated[AsyncSession, Depends(get_session)]
):
    file_storage = await get_image_by_pixel_hash(pixel_hash, db)
    if file_storage:
        image_bytes: bytes = await get_tile_from_dzi(file_storage, zoom, x, y)
        return Response(content=image_bytes, media_type="image/jpeg")
    else:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.IMAGE_NOT_FOUND,
            message=ErrorCode.IMAGE_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
        )


@images_route(
    "/{pixel_hash}",
    summary="Get file image by pixel hash",
    responses={200: {"content": {"image/jpeg": {}}}},
    response_class=Response,
    override_404=IMAGE_NOT_FOUND_RESPONSE,
)
async def get_image_full(pixel_hash: str, db: Annotated[AsyncSession, Depends(get_session)]):
    file = await get_image_by_pixel_hash(pixel_hash, db)
    if file:
        image_bytes: bytes = await get_image(file)
        media_type = file.mime if is_web_format(file) else "image/jpeg"
        return Response(content=image_bytes, media_type=media_type)
    else:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.IMAGE_NOT_FOUND,
            message=ErrorCode.IMAGE_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
        )


@images_route(
    "/{pixel_hash}/metadata",
    summary="Raw metadata by pixel hash",
    override_404=RAW_METADATA_NOT_FOUND_RESPONSE,
)
async def get_raw_metadata(pixel_hash: str, db: Annotated[AsyncSession, Depends(get_session)]):
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
    summary="Selected photography metadata by pixel hash",
    override_404=PHOTOGRAPHY_METADATA_NOT_FOUND_RESPONSE,
    response_model=PhotographyMetadata,
)
async def get_photography_metadata(
    pixel_hash: str, db: Annotated[AsyncSession, Depends(get_session)]
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
