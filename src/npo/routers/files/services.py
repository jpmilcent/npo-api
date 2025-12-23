import hashlib
import os

import exiftool
from fastapi import UploadFile

from npo import config
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
    storage_path = os.path.join(config.settings.storage_dir, file.hash_dir, file.hash_file)
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    os.rename(file.path, storage_path)
    file.path = storage_path


async def extract_metadata(file: File) -> dict:
    infos = {}
    with exiftool.ExifToolHelper() as et:
        metadata = et.get_tags(file.path, tags=["ImageWidth", "ImageHeight"])
        for d in metadata:
            infos[file.name] = d
    return infos


async def store_file_infos(file: File) -> None:
    pass  # To be implemented: store file infos in the database
