import hashlib
import os
from zipfile import ZipFile

import exiftool
import pyvips
from fastapi import UploadFile
from pyvips.enums import ForeignDzContainer, ForeignDzDepth, ForeignDzLayout
from sqlalchemy.ext.asyncio import AsyncSession

from npo import config
from npo.core.file import get_file_by_hash
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
    step: int = config.settings.hash_dir_step
    chunks = [file.hash[i : i + step] for i in range(0, len(file.hash), step)]

    for part, chunk in enumerate(chunks):
        if part < config.settings.hash_dir_parts_count:
            file.hash_dir += chunk + "/"
        else:
            file.hash_file += chunk


async def move_file(file: File) -> None:
    # TODO: Use file mime type to determine file extension
    storage_path = os.path.join(config.settings.storage_dir, file.hash_dir, file.hash_file + ".jpg")
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    os.rename(file.path, storage_path)
    file.path = storage_path


async def extract_metadata(file: File) -> None:
    with exiftool.ExifToolHelper() as et:
        metadata = et.get_metadata(file.path)
        for item in metadata:
            file.meta_data = item
            file.orientation = item.get("EXIF:Orientation")


async def store_file_infos(file: File, db: AsyncSession) -> None:
    file_storage = await get_file_by_hash(file.hash, db)

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


async def create_dzi(file: File) -> None:
    img = pyvips.Image.new_from_file(file.path)
    img = img.autorot()
    dzi_path = config.settings.storage_dir + file.hash_dir + file.hash_file + ".szi"
    img.dzsave(
        dzi_path,
        layout=ForeignDzLayout.GOOGLE,
        tile_size=256,
        overlap=1,
        suffix=".jpg",
        depth=ForeignDzDepth.ONETILE,
        container=ForeignDzContainer.ZIP,
        Q=85,
    )


async def get_tile_from_dzi(file: FileStorage, zoom: int, x: int, y: int) -> bytes | None:
    dzi_path = config.settings.storage_dir + file.hash_dir + file.hash_file + ".szi"
    if not os.path.exists(dzi_path):
        return None

    with ZipFile(dzi_path, "r") as zip_file:
        tile_path = f"{file.hash_file}/{zoom}/{x}/{y}.jpg"
        try:
            with zip_file.open(tile_path) as tile_file:
                return tile_file.read()
        except KeyError:
            return None


async def get_image(file: FileStorage) -> bytes | None:
    img_path = config.settings.storage_dir + file.hash_dir + file.hash_file + ".jpg"

    try:
        with open(img_path, "rb") as img_file:
            return img_file.read()
    except FileNotFoundError:
        return None
