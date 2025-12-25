import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from npo import config
from npo.core.file import get_file_by_hash
from npo.database import get_session
from npo.routers.files.schemas import File
from npo.routers.files.services import (
    compute_hash,
    compute_hash_pathes,
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
)
async def compute_upload_files(files: list[UploadFile], db: AsyncSession = Depends(get_session)):
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
        await compute_hash(file)
        await compute_hash_pathes(file)
        await move_file(file)
        await extract_metadata(file)
        await store_file_infos(file, db)
        await create_dzi(file)
        infos[file.name] = file.__dict__

    return infos


@files_router.get(
    "/{file_hash}/{zoom}/{x}/{y}.jpg",
    summary="Get tile image by hash, zoom level and coordinates",
    responses={200: {"content": {"image/jpeg": {}}}},
    response_class=Response,
)
async def get_image_tile(
    file_hash: str, zoom: int, x: int, y: int, db: AsyncSession = Depends(get_session)
):
    file_storage = await get_file_by_hash(file_hash, db)
    if file_storage:
        image_bytes: bytes = await get_tile_from_dzi(file_storage, zoom, x, y)
        return Response(content=image_bytes, media_type="image/jpeg")
    else:
        raise HTTPException(status_code=404, detail="File not found")


@files_router.get(
    "/{file_hash}",
    summary="Get file image by hash",
    responses={200: {"content": {"image/jpeg": {}}}},
    response_class=Response,
)
async def get_image_full(file_hash: str, db: AsyncSession = Depends(get_session)):
    file_storage = await get_file_by_hash(file_hash, db)
    if file_storage:
        image_bytes: bytes = await get_image(file_storage)
        return Response(content=image_bytes, media_type=file_storage.mime)
    else:
        raise HTTPException(status_code=404, detail="File not found")
