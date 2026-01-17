from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from npo.common.decorators import NpoApiRoute
from npo.core.constants import ErrorCode
from npo.core.database import get_session
from npo.core.exceptions import APIException
from npo.files.crud import get_file_by_pixel_hash, get_files_list
from npo.files.services import (
    build_file_infos,
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
    store_file_infos,
)
from npo.metadata.services import (
    _format_aperture,
    _format_color_space,
    _format_exposure_compensation,
    _format_exposure_mode,
    _format_exposure_program,
    _format_flash,
    _format_focal_length,
    _format_metering_mode,
    _format_orientation,
    _format_pixels,
    _format_scene_capture_type,
    _format_scene_type,
    _format_shutter_speed,
    _format_white_balance,
)

FILE_NOT_FOUND_RESPONSE = {
    "description": "File not found",
    "code": ErrorCode.FILE_NOT_FOUND,
    "message": ErrorCode.FILE_NOT_FOUND.message,
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

files_router = APIRouter(
    prefix="/files",
    tags=["files"],
)
files_route = NpoApiRoute(files_router)


@files_router.get(
    "/",
    summary="Get paginated files list",
)
async def root(
    db: Annotated[AsyncSession, Depends(get_session)],
    page: int = 1,
    size: int = 100,
):
    skip = (page - 1) * size
    limit = size
    files, total = await get_files_list(db, skip=skip, limit=limit)
    return {
        "meta": {
            "pagination": {
                "total_items": total,
                "total_pages": (total + limit - 1) // limit,
                "current_page": page,
                "items_per_page": limit,
            }
        },
        "data": files,
    }


@files_router.post(
    "/upload",
    summary="Upload files",
    status_code=status.HTTP_201_CREATED,
)
async def compute_upload_files(
    files: list[UploadFile], db: Annotated[AsyncSession, Depends(get_session)]
):
    infos = {}
    # Process each received files
    for upload_file in files:
        file = await build_file_infos(upload_file)

        await save_file(upload_file, file)

        await compute_perceptual_hash(file)
        await check_duplicates_by_perceptual_hash(file, db)
        await extract_metadata(file)
        await check_duplicates_by_image_unique_id(file, db)

        await compute_hash(file)
        await compute_pixel_hash(file)
        await compute_hash_pathes(file)
        await move_file(file)
        await store_file_infos(file, db)
        await create_dzi(file)
        infos[file.name] = file.__dict__

    return infos


@files_route(
    "/{pixel_hash}/{zoom}/{x}/{y}.jpg",
    summary="Get tile image by pixel hash, zoom level and coordinates",
    responses={200: {"content": {"image/jpeg": {}}}},
    response_class=Response,
    override_404=FILE_NOT_FOUND_RESPONSE,
)
async def get_image_tile(
    pixel_hash: str, zoom: int, x: int, y: int, db: Annotated[AsyncSession, Depends(get_session)]
):
    file_storage = await get_file_by_pixel_hash(pixel_hash, db)
    if file_storage:
        image_bytes: bytes = await get_tile_from_dzi(file_storage, zoom, x, y)
        return Response(content=image_bytes, media_type="image/jpeg")
    else:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.FILE_NOT_FOUND,
            message=ErrorCode.FILE_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
        )


@files_route(
    "/{pixel_hash}",
    summary="Get file image by pixel hash",
    responses={200: {"content": {"image/jpeg": {}}}},
    response_class=Response,
    override_404=FILE_NOT_FOUND_RESPONSE,
)
async def get_image_full(pixel_hash: str, db: Annotated[AsyncSession, Depends(get_session)]):
    file = await get_file_by_pixel_hash(pixel_hash, db)
    if file:
        image_bytes: bytes = await get_image(file)
        media_type = file.mime if is_web_format(file) else "image/jpeg"
        return Response(content=image_bytes, media_type=media_type)
    else:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.FILE_NOT_FOUND,
            message=ErrorCode.FILE_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
        )


@files_route(
    "/{pixel_hash}/metadata",
    summary="Raw metadata by pixel hash",
    override_404=RAW_METADATA_NOT_FOUND_RESPONSE,
)
async def get_raw_metadata(pixel_hash: str, db: Annotated[AsyncSession, Depends(get_session)]):
    file_storage = await get_file_by_pixel_hash(pixel_hash, db)
    if file_storage:
        return file_storage.meta_data
    else:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.RAW_METADATA_NOT_FOUND,
            message=ErrorCode.RAW_METADATA_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
        )


@files_route(
    "/{pixel_hash}/metadata/photography",
    summary="Selected photography metadata by pixel hash",
    override_404=PHOTOGRAPHY_METADATA_NOT_FOUND_RESPONSE,
)
async def get_photography_metadata(
    pixel_hash: str, db: Annotated[AsyncSession, Depends(get_session)]
):
    file_storage = await get_file_by_pixel_hash(pixel_hash, db)
    meta = file_storage.meta_data if file_storage else None
    if meta:
        return {
            "cameraMaker": meta.get("EXIF:Make"),
            "cameraModel": meta.get("EXIF:Model"),
            "lensModel": meta.get("EXIF:LensModel"),
            "focalLength": _format_focal_length(meta.get("EXIF:FocalLength")),
            "focalLengthIn35mmFormat": _format_focal_length(
                meta.get("EXIF:FocalLengthIn35mmFormat")
            ),
            "aperture": _format_aperture(meta.get("EXIF:FNumber")),
            "shutterSpeed": _format_shutter_speed(meta.get("EXIF:ExposureTime")),
            "iso": meta.get("EXIF:ISO") or meta.get("EXIF:ISOSpeedRatings"),
            "flash": _format_flash(meta.get("EXIF:Flash")),
            "imageWidth": _format_pixels(
                meta.get("File:ImageWidth") or meta.get("EXIF:ExifImageWidth")
            ),
            "imageHeight": _format_pixels(
                meta.get("File:ImageHeight") or meta.get("EXIF:ExifImageHeight")
            ),
            "orientation": _format_orientation(meta.get("EXIF:Orientation")),
            "whiteBalance": _format_white_balance(meta.get("EXIF:WhiteBalance")),
            "exposureProgram": _format_exposure_program(meta.get("EXIF:ExposureProgram")),
            "exposureMode": _format_exposure_mode(meta.get("EXIF:ExposureMode")),
            "exposureCompensation": _format_exposure_compensation(
                meta.get("EXIF:ExposureCompensation")
            ),
            "meteringMode": _format_metering_mode(meta.get("EXIF:MeteringMode")),
            "sceneCaptureType": _format_scene_capture_type(meta.get("EXIF:SceneCaptureType")),
            "sceneType": _format_scene_type(meta.get("EXIF:SceneType")),
            "colorSpace": _format_color_space(meta.get("EXIF:ColorSpace")),
        }
    else:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ErrorCode.PHOTOGRAPHY_METADATA_NOT_FOUND,
            message=ErrorCode.PHOTOGRAPHY_METADATA_NOT_FOUND.formatMsg(pixel_hash=pixel_hash),
        )


@files_router.get("/{path:path}", include_in_schema=False)
async def files_catch_all(path: str):
    raise APIException(
        status_code=status.HTTP_404_NOT_FOUND,
        code=ErrorCode.FILES_WEBSERVICE_NOT_FOUND,
        message=ErrorCode.FILES_WEBSERVICE_NOT_FOUND.formatMsg(path=path),
    )
