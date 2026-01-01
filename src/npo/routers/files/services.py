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


async def compute_pixel_hash(file: File) -> None:
    """
    Calcule un hash BLAKE2b basé sur les pixels bruts de l'image via pyvips.
    Ignore les métadonnées (EXIF, etc).
    """
    # access="sequential" optimise la lecture pour un seul passage
    img = pyvips.Image.new_from_file(file.path, access="sequential")

    # write_to_memory() force le décodage et retourne les bytes des pixels (RGB/RGBA...)
    data = img.write_to_memory()
    # digest_size=16 produit 128 bits (32 hex chars), format identique à MD5 mais plus rapide/sûr
    file.pixel_hash = hashlib.blake2b(data, digest_size=16).hexdigest()


async def compute_perceptual_hash(file: File) -> None:
    """
    Calcule un hash perceptuel (dHash) en utilisant pyvips.
    Résistant aux redimensionnements et à la compression.
    """
    # Chargement et redimensionnement en 9x8 pixels (force la taille sans conserver le ratio)
    # Utilisation de access="sequential" pour forcer le mode flux (streaming) et économiser la mémoire
    img = pyvips.Image.new_from_file(file.path, access="sequential")
    img = img.thumbnail_image(9, height=8, size="force")

    # Conversion en noir et blanc
    img = img.colourspace("b-w")

    # Récupération des données brutes des pixels (9x8 = 72 octets)
    pixels = img.write_to_memory()

    hash_val = 0
    # On parcourt les 8 lignes
    for row in range(8):
        # On parcourt les 8 colonnes de gauche à droite
        for col in range(8):
            # Si le pixel de gauche est plus clair que celui de droite, on met le bit à 1
            if pixels[row * 9 + col] > pixels[row * 9 + col + 1]:
                hash_val |= 1 << (63 - (row * 8 + col))

    file.perceptual_hash = f"{hash_val:016x}"


async def compute_hash_pathes(file: File) -> None:
    step: int = config.settings.hash_dir_step
    chunks = [file.pixel_hash[i : i + step] for i in range(0, len(file.pixel_hash), step)]

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
            file.image_unique_id = item.get("EXIF:ImageUniqueID")


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
