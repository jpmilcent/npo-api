import hashlib
import os

import exiftool
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from npo import config
from npo.models.file import File as FileStorage
from npo.routers.files.schemas import File


async def save_file(upload_file: UploadFile, file: File):
    try:
        with open(file.path, "wb") as buffer:
            while True:
                chunk = await upload_file.read(1024)
                if not chunk:
                    break
                buffer.write(chunk)
    except IOError:
        return {"message": "There was an error uploading the file"}
    finally:
        await upload_file.close()


async def compute_hash(file: File) -> None:
    with open(file.path, "rb") as file_to_hash:
        data = file_to_hash.read()
        file.hash = hashlib.md5(data).hexdigest()


async def compute_hash_pathes(file: File) -> None:
    step: int = 2
    chunks = [file.hash[i : i + step] for i in range(0, len(file.hash), step)]

    for part, chunk in enumerate(chunks):
        if part < 6:
            file.hash_dir += chunk + "/"
        else:
            file.hash_file += chunk


async def move_file(file: File) -> None:
    storage_path = os.path.join(config.settings.storage_dir, file.hash_dir, file.hash_file + ".jpg")
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    os.rename(file.path, storage_path)
    file.path = storage_path


async def extract_metadata(file: File) -> None:
    with exiftool.ExifToolHelper() as et:
        metadata = et.get_tags(file.path, tags=["ImageWidth", "ImageHeight"])
        for item in metadata:
            file.meta_data = item


async def store_file_infos(file: File, db: AsyncSession) -> None:
    stmt = select(FileStorage).filter_by(hash=file.hash)
    result = await db.execute(stmt)
    file_storage = result.scalar_one_or_none()

    if file_storage:
        data = file.model_dump(exclude_none=True)
        data.pop("id", None)
        for key, value in data.items():
            setattr(file_storage, key, value)
    else:
        file_storage = FileStorage(**file.__dict__)
        db.add(file_storage)

    await db.commit()
    await db.refresh(file_storage)
