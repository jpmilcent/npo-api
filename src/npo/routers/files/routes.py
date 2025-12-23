import os

from fastapi import APIRouter, UploadFile

from npo import config
from npo.routers.files.schemas import File
from npo.routers.files.services import (
    compute_hash,
    compute_hash_pathes,
    extract_metadata,
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
    summary="Manipulate files",
)
async def compute_upload_files(files: list[UploadFile]):
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
        file.metadata = await extract_metadata(file)
        await store_file_infos(file)
        infos[file.name] = file.__dict__

    return infos
