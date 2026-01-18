import asyncio
import hashlib
import logging
import mimetypes
import os
from datetime import datetime
from zipfile import ZipFile

import exiftool
import magic
import pyvips
from fastapi import UploadFile, status
from fastapi_babel import _
from pyvips.enums import ForeignDzContainer, ForeignDzDepth, ForeignDzLayout
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core import config
from npo.core.exceptions import APIException
from npo.modules.images.crud import (
    get_image_by_image_unique_id,
    get_image_by_perceptual_hash,
    get_image_by_pixel_hash,
)
from npo.modules.images.models import Image as ImageStorage
from npo.modules.images.schemas import Image

logger = logging.getLogger(__name__)


async def build_image_infos(upload_file: UploadFile) -> Image:
    mime_type = await extract_mime_type(upload_file)

    return Image(
        name=upload_file.filename,
        path=os.path.join(config.settings.uploads_dir, upload_file.filename),
        size=upload_file.size,
        mime=mime_type,
    )


async def extract_mime_type(file: UploadFile) -> str:
    content_sample = await file.read(2048)
    mime_type = magic.from_buffer(content_sample, mime=True)

    # Since DNG is often interpreted as TIFF, magic function may return "image/tiff".
    # We correct this if extension is explicit.fix
    if mime_type == "image/tiff" and file.filename.lower().endswith(".dng"):
        mime_type = "image/x-adobe-dng"

    await file.seek(0)
    return mime_type


async def save_file(upload_file: UploadFile, file: Image):
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


async def compute_hash(file: Image) -> None:
    with open(file.path, "rb") as file_to_hash:
        data = file_to_hash.read()
        file.file_hash = hashlib.md5(data).hexdigest()


def _compute_pixel_hash_sync(image: Image, preview_bytes: bytes | None = None) -> str:
    # For RAW/DNG, we must force demosaicing (development) to get the actual visual content.
    # Converting to sRGB ensures the RAW data is developed into visible pixels.
    if preview_bytes:
        img = pyvips.Image.new_from_buffer(preview_bytes, "")
    elif is_web_format(image):
        img = pyvips.Image.new_from_file(image.path, access="sequential")
    else:
        img = pyvips.Image.new_from_file(image.path)
        img = img.colourspace("srgb")

    file_hash = hashlib.blake2b(digest_size=16)

    # Process image in chunks using crop() which supports sequential streaming
    chunk_height = 512

    for y in range(0, img.height, chunk_height):
        height_to_process = min(chunk_height, img.height - y)
        data = img.crop(0, y, img.width, height_to_process).write_to_memory()
        file_hash.update(data)

    return file_hash.hexdigest()


async def compute_pixel_hash(file: Image) -> None:
    """
    Computes a BLAKE2b hash based on raw image pixels via pyvips.
    Ignores metadata (EXIF, etc).
    """
    try:
        preview_bytes = None
        if not is_web_format(file):
            preview_bytes = await extract_jpeg_preview(file)

        loop = asyncio.get_running_loop()
        file.pixel_hash = await loop.run_in_executor(
            None, _compute_pixel_hash_sync, file, preview_bytes
        )
    except pyvips.Error as e:
        logger.error(f"Error computing pixel hash for {file.path}: {e}")
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="IMAGE_DECODING_ERROR",
            message=(
                f"Unable to decode image file {file.name}. "
                "The file might be corrupted or unsupported."
            ),
        ) from e


def _compute_perceptual_hash_sync(path: str | None, data: bytes | None) -> str:
    img = None
    if data:
        img = pyvips.Image.new_from_buffer(data, "")
    elif path:
        img = pyvips.Image.new_from_file(path, access="sequential")

    if img is None:
        raise pyvips.Error("No image source available for perceptual hash")

    img = img.thumbnail_image(9, height=8, size="force")
    img = img.colourspace("b-w")
    pixels = img.write_to_memory()

    hash_val = 0
    for row in range(8):
        for col in range(8):
            if pixels[row * 9 + col] > pixels[row * 9 + col + 1]:
                hash_val |= 1 << (63 - (row * 8 + col))

    return f"{hash_val:016x}"


async def compute_perceptual_hash(image: Image) -> None:
    """
    Computes a perceptual hash (dHash) using pyvips.
    Resistant to resizing and compression.
    """
    try:
        web_format = is_web_format(image)
        preview_bytes = None
        path = None

        if web_format:
            path = image.path
        else:
            preview_bytes = await extract_jpeg_preview(image)

        loop = asyncio.get_running_loop()
        image.perceptual_hash = await loop.run_in_executor(
            None, _compute_perceptual_hash_sync, path, preview_bytes
        )
    except pyvips.Error as e:
        logger.error(f"Error computing perceptual hash for {image.path}: {e}")
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="IMAGE_PROCESSING_ERROR",
            message=f"Unable to process image file {image.name} for perceptual hashing.",
        ) from e


def is_web_format(image: Image) -> bool:
    is_web_format = (image.mime in ["image/jpeg", "image/png", "image/gif", "image/webp"]) or (
        image.name.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
    )
    return is_web_format


async def extract_jpeg_preview(image: Image) -> bytes | None:
    preview_bytes = None
    # On essaie d'abord PreviewImage, puis JpgFromRaw si le premier échoue
    for tag in ["-PreviewImage", "-JpgFromRaw"]:
        try:
            # Extraction binaire (-b) du tag via exiftool
            # Utilisation de asyncio pour ne pas bloquer la boucle d'événements
            proc = await asyncio.create_subprocess_exec(
                "exiftool",
                "-b",
                tag,
                image.path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024 * 50,  # Augmentation du buffer (50 Mo) pour les grosses images
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except OSError:
                    pass
                continue

            if proc.returncode != 0:
                logger.warning(
                    f"Exiftool error for {image.path} with tag {tag}: {stderr.decode().strip()}"
                )

            if proc.returncode == 0 and stdout:
                preview_bytes = stdout
                break
        except Exception as e:
            logger.warning(f"Error extracting preview for {image.path} with tag {tag}: {e}")
    return preview_bytes


async def check_duplicates_by_perceptual_hash(image: Image, db: AsyncSession) -> None:
    if await get_image_by_perceptual_hash(image.perceptual_hash, db):
        raise APIException(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_PERCEPTUAL_HASH",
            message=_("Image {file_name} with perceptual hash {hash} already exists.").format(
                file_name=image.name,
                hash=image.perceptual_hash,
            ),
        )


async def compute_hash_pathes(image: Image) -> None:
    step: int = config.settings.hash_dir_step
    chunks = [image.pixel_hash[i : i + step] for i in range(0, len(image.pixel_hash), step)]

    for part, chunk in enumerate(chunks):
        if part < config.settings.hash_dir_parts_count:
            image.path_hash_dir += chunk + "/"
        else:
            image.path_hash_file += chunk


async def move_file(image: Image) -> None:
    extension = await get_file_extension(image)
    storage_path = os.path.join(
        config.settings.storage_dir, image.path_hash_dir, image.path_hash_file + extension
    )
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    os.rename(image.path, storage_path)
    image.path = storage_path


async def get_file_extension(image: Image) -> str:
    if not image.mime:
        return ""
    extension = mimetypes.guess_extension(image.mime)
    if extension is None and image.mime.lower() == "image/x-adobe-dng":
        extension = ".dng"
    return extension if extension else ""


async def extract_metadata(image: Image) -> None:
    with exiftool.ExifToolHelper() as et:
        metadata = et.get_metadata(image.path, params=["-n"])
        for item in metadata:
            image.meta_data = item
            image.orientation = item.get("EXIF:Orientation")
            image.image_unique_id = item.get("EXIF:ImageUniqueID")

            # GPS Data
            check_gps_map_datum(image, item)
            image.latitude = extract_metadata_latitude(item)
            image.longitude = extract_metadata_longitude(item)
            image.altitude = extract_metadata_altitude(item)

            # DateTime Data
            image.datetime_shooting = parse_exif_date(item.get("EXIF:DateTimeOriginal"))
            image.datetime_digitized = parse_exif_date(item.get("EXIF:DateTimeDigitized"))


def check_gps_map_datum(image: Image, metadata: dict) -> None:
    gps_datum = metadata.get("EXIF:GPSMapDatum")
    if gps_datum and gps_datum != "WGS-84":
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="UNSUPPORTED_GPS_DATUM",
            message=(
                f"Image {image.name} has unsupported GPS Map Datum: {gps_datum}. "
                "Only WGS-84 is supported."
            ),
        )


def extract_metadata_altitude(metadata: dict) -> float | None:
    altitude = metadata.get("EXIF:GPSAltitude")
    if altitude is not None and metadata.get("EXIF:GPSAltitudeRef") == 1:
        return -1.0 * altitude
    return altitude


def extract_metadata_latitude(metadata: dict) -> float | None:
    latitude = metadata.get("EXIF:GPSLatitude")
    # If the reference is "S" (South), the latitude is negative
    if latitude is not None and metadata.get("EXIF:GPSLatitudeRef") == "S":
        return -1.0 * latitude
    return latitude


def extract_metadata_longitude(metadata: dict) -> float | None:
    longitude = metadata.get("EXIF:GPSLongitude")
    # If the reference is "W" (West), the longitude is negative
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


async def check_duplicates_by_image_unique_id(image: Image, db: AsyncSession) -> None:
    if await get_image_by_image_unique_id(image.image_unique_id, db):
        raise APIException(
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_IMAGE_UNIQUE_ID",
            message=_(
                "Image {file_name} with image unique ID {image_unique_id} already exists."
            ).format(
                file_name=image.name,
                image_unique_id=image.image_unique_id,
            ),
        )


async def store_image_infos(image: Image, db: AsyncSession) -> None:
    file_storage = await get_image_by_pixel_hash(image.pixel_hash, db)

    if file_storage:
        data = image.model_dump(exclude_none=True)
        data.pop("id", None)
        for key, value in data.items():
            setattr(file_storage, key, value)
    else:
        file_storage = ImageStorage(**image.__dict__)
        db.add(file_storage)

    await db.commit()
    await db.refresh(file_storage)


async def create_dzi(image: Image) -> None:
    web_format = is_web_format(image)
    if not web_format:
        preview_bytes = await extract_jpeg_preview(image)
        if preview_bytes:
            img = pyvips.Image.new_from_buffer(preview_bytes, "")
    else:
        img = pyvips.Image.new_from_file(image.path)
    img = img.autorot()
    dzi_path = config.settings.storage_dir + image.path_hash_dir + image.path_hash_file + ".szi"
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


async def get_tile_from_dzi(image: ImageStorage, zoom: int, x: int, y: int) -> bytes | None:
    dzi_path = config.settings.storage_dir + image.path_hash_dir + image.path_hash_file + ".szi"
    if not os.path.exists(dzi_path):
        return None

    with ZipFile(dzi_path, "r") as zip_file:
        tile_path = f"{image.path_hash_file}/{zoom}/{x}/{y}.jpg"
        try:
            with zip_file.open(tile_path) as tile_file:
                return tile_file.read()
        except KeyError:
            return None


async def get_image(image: ImageStorage) -> bytes | None:
    web_format = is_web_format(image)
    if not web_format:
        return await extract_jpeg_preview(image)
    else:
        try:
            extension = await get_file_extension(image)
            img_path = (
                config.settings.storage_dir + image.path_hash_dir + image.path_hash_file + extension
            )
            with open(img_path, "rb") as img_file:
                return img_file.read()
        except FileNotFoundError:
            return None
