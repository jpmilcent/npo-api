import hashlib
import os
from datetime import datetime
from zipfile import ZipFile

import exiftool
import pyvips
from fastapi import HTTPException, UploadFile, status
from pyvips.enums import ForeignDzContainer, ForeignDzDepth, ForeignDzLayout
from sqlalchemy.ext.asyncio import AsyncSession

from npo import config
from npo.core.file import (
    get_file_by_image_unique_id,
    get_file_by_perceptual_hash,
    get_file_by_pixel_hash,
)
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
        file.file_hash = hashlib.md5(data).hexdigest()


async def compute_pixel_hash(file: File) -> None:
    """
    Computes a BLAKE2b hash based on raw image pixels via pyvips.
    Ignores metadata (EXIF, etc).
    """
    img = pyvips.Image.new_from_file(file.path, access="sequential")

    # write_to_memory() forces decoding and returns pixel bytes (RGB/RGBA...)
    data = img.write_to_memory()
    # digest_size=16 produces 128 bits (32 hex chars), same format as MD5 but faster/safer
    file.pixel_hash = hashlib.blake2b(data, digest_size=16).hexdigest()


async def compute_perceptual_hash(file: File) -> None:
    """
    Computes a perceptual hash (dHash) using pyvips.
    Resistant to resizing and compression.
    """
    # Load and resize to 9x8 pixels (force size without preserving aspect ratio)
    # Use access="sequential" to force streaming mode and save memory
    img = pyvips.Image.new_from_file(file.path, access="sequential")
    img = img.thumbnail_image(9, height=8, size="force")

    # Convert to black and white
    img = img.colourspace("b-w")

    # Retrieve raw pixel data (9x8 = 72 bytes)
    pixels = img.write_to_memory()

    hash_val = 0
    # Iterate over the 8 rows
    for row in range(8):
        # Iterate over the 8 columns from left to right
        for col in range(8):
            # If the left pixel is brighter than the right one, set the bit to 1
            if pixels[row * 9 + col] > pixels[row * 9 + col + 1]:
                hash_val |= 1 << (63 - (row * 8 + col))

    file.perceptual_hash = f"{hash_val:016x}"


async def check_duplicates_by_perceptual_hash(file: File, db: AsyncSession) -> None:
    if await get_file_by_perceptual_hash(file.perceptual_hash, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_PERCEPTUAL_HASH",
                "message": (
                    f"File {file.name} with perceptual hash {file.perceptual_hash} already exists."
                ),
            },
        )


async def compute_hash_pathes(file: File) -> None:
    step: int = config.settings.hash_dir_step
    chunks = [file.pixel_hash[i : i + step] for i in range(0, len(file.pixel_hash), step)]

    for part, chunk in enumerate(chunks):
        if part < config.settings.hash_dir_parts_count:
            file.path_hash_dir += chunk + "/"
        else:
            file.path_hash_file += chunk


async def move_file(file: File) -> None:
    # TODO: Use file mime type to determine file extension
    storage_path = os.path.join(
        config.settings.storage_dir, file.path_hash_dir, file.path_hash_file + ".jpg"
    )
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    os.rename(file.path, storage_path)
    file.path = storage_path


async def extract_metadata(file: File) -> None:
    with exiftool.ExifToolHelper() as et:
        metadata = et.get_metadata(file.path, params=["-n"])
        for item in metadata:
            file.meta_data = item
            file.orientation = item.get("EXIF:Orientation")
            file.image_unique_id = item.get("EXIF:ImageUniqueID")

            # GPS Data
            check_gps_map_datum(file, item)
            file.latitude = extract_metadata_latitude(item)
            file.longitude = extract_metadata_longitude(item)
            file.altitude = extract_metadata_altitude(item)

            # DateTime Data
            file.datetime_shooting = parse_exif_date(item.get("EXIF:DateTimeOriginal"))
            file.datetime_digitized = parse_exif_date(item.get("EXIF:DateTimeDigitized"))


def check_gps_map_datum(file: File, metadata: dict) -> None:
    gps_datum = metadata.get("EXIF:GPSMapDatum")
    if gps_datum and gps_datum != "WGS-84":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNSUPPORTED_GPS_DATUM",
                "message": (
                    f"File {file.name} has unsupported GPS Map Datum: {gps_datum}. "
                    "Only WGS-84 is supported."
                ),
            },
        )


def extract_metadata_altitude(metadata: dict) -> float | None:
    altitude = metadata.get("EXIF:GPSAltitude")
    if altitude is not None and metadata.get("EXIF:GPSAltitudeRef") == 1:
        return -1.0 * altitude
    return altitude


def extract_metadata_latitude(metadata: dict) -> float | None:
    latitude = metadata.get("EXIF:GPSLatitude")
    # Si la référence est "S" (South), la latitude est négative
    if latitude is not None and metadata.get("EXIF:GPSLatitudeRef") == "S":
        return -1.0 * latitude
    return latitude


def extract_metadata_longitude(metadata: dict) -> float | None:
    longitude = metadata.get("EXIF:GPSLongitude")
    # Si la référence est "W" (West), la longitude est négative
    if longitude is not None and metadata.get("EXIF:GPSLongitudeRef") == "W":
        return -1.0 * longitude
    return longitude


def parse_exif_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


async def check_duplicates_by_image_unique_id(file: File, db: AsyncSession) -> None:
    if await get_file_by_image_unique_id(file.image_unique_id, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_IMAGE_UNIQUE_ID",
                "message": (
                    f"File {file.name} with image unique ID {file.image_unique_id} already exists."
                ),
            },
        )


async def store_file_infos(file: File, db: AsyncSession) -> None:
    file_storage = await get_file_by_pixel_hash(file.pixel_hash, db)

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
    dzi_path = config.settings.storage_dir + file.path_hash_dir + file.path_hash_file + ".szi"
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
    dzi_path = config.settings.storage_dir + file.path_hash_dir + file.path_hash_file + ".szi"
    if not os.path.exists(dzi_path):
        return None

    with ZipFile(dzi_path, "r") as zip_file:
        tile_path = f"{file.path_hash_file}/{zoom}/{x}/{y}.jpg"
        try:
            with zip_file.open(tile_path) as tile_file:
                return tile_file.read()
        except KeyError:
            return None


async def get_image(file: FileStorage) -> bytes | None:
    img_path = config.settings.storage_dir + file.path_hash_dir + file.path_hash_file + ".jpg"

    try:
        with open(img_path, "rb") as img_file:
            return img_file.read()
    except FileNotFoundError:
        return None
