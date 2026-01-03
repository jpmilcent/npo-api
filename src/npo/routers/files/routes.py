import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from npo import config
from npo.core.file import get_file_by_pixel_hash
from npo.database import get_session
from npo.routers.files.schemas import File
from npo.routers.files.services import (
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
    move_file,
    save_file,
    store_file_infos,
)

files_router = APIRouter(
    prefix="/files",
    tags=["files"],
    responses={404: {"description": "Not found"}},
)


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
        file = File(
            name=upload_file.filename,
            path=os.path.join(config.settings.uploads_dir, upload_file.filename),
            size=upload_file.size,
            mime=upload_file.content_type,
        )

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


@files_router.get(
    "/{pixel_hash}/{zoom}/{x}/{y}.jpg",
    summary="Get tile image by pixel hash, zoom level and coordinates",
    responses={200: {"content": {"image/jpeg": {}}}},
    response_class=Response,
)
async def get_image_tile(
    pixel_hash: str, zoom: int, x: int, y: int, db: Annotated[AsyncSession, Depends(get_session)]
):
    file_storage = await get_file_by_pixel_hash(pixel_hash, db)
    if file_storage:
        image_bytes: bytes = await get_tile_from_dzi(file_storage, zoom, x, y)
        return Response(content=image_bytes, media_type="image/jpeg")
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "FILE_NOT_FOUND",
                "message": f"File {pixel_hash} not found",
            },
        )


@files_router.get(
    "/{pixel_hash}",
    summary="Get file image by hash",
    responses={200: {"content": {"image/jpeg": {}}}},
    response_class=Response,
)
async def get_image_full(pixel_hash: str, db: Annotated[AsyncSession, Depends(get_session)]):
    file_storage = await get_file_by_pixel_hash(pixel_hash, db)
    if file_storage:
        image_bytes: bytes = await get_image(file_storage)
        return Response(content=image_bytes, media_type=file_storage.mime)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "FILE_NOT_FOUND",
                "message": f"File {pixel_hash} not found",
            },
        )
