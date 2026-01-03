from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core.file import get_file_by_pixel_hash
from npo.database import get_session
from npo.routers.metadata.services import (
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
from npo.routers.utils import APIException, create_route_decorator

RAW_METADATA_NOT_FOUND = {
    "description": "Raw metadata not found",
    "code": "RAW_METADATA_NOT_FOUND",
    "message": "Raw metadata for file {pixel_hash} not found.",
}

PHOTOGRAPHY_METADATA_NOT_FOUND = {
    "description": "Photography metadata not found",
    "code": "PHOTOGRAPHY_METADATA_NOT_FOUND",
    "message": "Photography metadata for file {pixel_hash} not found.",
}

metadata_router = APIRouter(
    prefix="/metadata",
    tags=["metadata"],
)


metadata_route = create_route_decorator(metadata_router)


@metadata_route(
    "/{pixel_hash}",
    summary="Raw metadata by pixel hash",
    override_404=RAW_METADATA_NOT_FOUND,
)
async def get_raw_metadata(pixel_hash: str, db: Annotated[AsyncSession, Depends(get_session)]):
    file_storage = await get_file_by_pixel_hash(pixel_hash, db)
    if file_storage:
        return file_storage.meta_data
    else:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=RAW_METADATA_NOT_FOUND["code"],
            message=RAW_METADATA_NOT_FOUND["message"].format(pixel_hash=pixel_hash),
        )


@metadata_route(
    "/{pixel_hash}/photography",
    summary="Selected photography metadata by pixel hash",
    override_404=PHOTOGRAPHY_METADATA_NOT_FOUND,
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
            code=PHOTOGRAPHY_METADATA_NOT_FOUND["code"],
            message=PHOTOGRAPHY_METADATA_NOT_FOUND["message"].format(pixel_hash=pixel_hash),
        )


@metadata_router.get("/{path:path}", include_in_schema=False)
async def metadata_catch_all(path: str):
    raise APIException(
        status_code=status.HTTP_404_NOT_FOUND,
        code="METADATA_WEBSERVICE_NOT_FOUND",
        message=f"Webservice /metadata/{path} requested not found.",
    )
