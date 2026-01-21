import asyncio
import contextlib
import hashlib
import logging
import mimetypes
import os
import shutil
from datetime import datetime
from zipfile import ZipFile

import exiftool
import magic
import pyvips
from fastapi import UploadFile
from pyvips.enums import ForeignDzContainer, ForeignDzDepth, ForeignDzLayout
from sqlalchemy.ext.asyncio import AsyncSession

from npo.core import config
from npo.core.constants import ErrorCode
from npo.modules.images.crud import (
    get_image_by_image_unique_id,
    get_image_by_perceptual_hash,
    get_image_by_pixel_hash,
)
from npo.modules.images.models import Image as ImageStorage
from npo.modules.images.schemas import Image

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Base class for domain exceptions."""

    def __init__(self, code: ErrorCode, **kwargs):
        self.code = code
        self.kwargs = kwargs


class DuplicateImageError(DomainError):
    """Exception raised when an image already exists."""

    pass


class InsufficientStorageError(DomainError):
    """Exception raised when there is not enough storage space."""

    pass


class FileTooLargeError(DomainError):
    """Exception raised when file size exceeds limit."""

    pass


class StorageError(DomainError):
    """Exception raised when storage operation fails."""

    pass


class ImageDecodingError(DomainError):
    """Exception raised when image decoding fails."""

    pass


class ImageProcessingError(DomainError):
    """Exception raised when image processing fails."""

    pass


class UnsupportedGpsDatumError(DomainError):
    """Exception raised when GPS datum is not supported."""

    pass


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
        logger.info(
            f"Correcting MIME type for {file.filename} from {mime_type} to image/x-adobe-dng"
        )
        mime_type = "image/x-adobe-dng"

    await file.seek(0)
    return mime_type


async def save_file(upload_file: UploadFile, file: Image):
    if file.size:
        check_max_upload_size(file.size)

    check_required_space(file)

    try:
        with open(file.path, "wb") as buffer:
            written_bytes = 0
            while True:
                chunk = await upload_file.read(1024)
                if not chunk:
                    break
                written_bytes += len(chunk)
                check_max_upload_size(written_bytes)
                buffer.write(chunk)
    except OSError as e:
        logger.exception(f"There was an error uploading the file {file.name}")
        raise StorageError(
            code=ErrorCode.FILE_UPLOAD_ERROR,
        ) from e
    except DomainError:
        clean_upload_file(file)
        raise
    finally:
        await upload_file.close()


def check_max_upload_size(file_size: int) -> None:
    """Check if the file size exceeds the maximum allowed limit (content-length)."""
    if file_size > config.backend_settings.max_upload_size:
        logger.error("File size exceeds the maximum allowed limit.")
        raise FileTooLargeError(
            code=ErrorCode.FILE_TOO_LARGE,
        )


def check_required_space(file: Image) -> None:
    _total, _used, free = shutil.disk_usage(os.path.dirname(file.path))
    required_space = config.backend_settings.upload_safety_buffer
    if file.size:
        required_space += file.size

    if free < required_space:
        logger.error(f"Not enough disk space ({free} bytes) to save the file.")
        raise InsufficientStorageError(
            code=ErrorCode.INSUFFICIENT_STORAGE,
        )


def clean_upload_file(file: Image):
    if os.path.exists(file.path):
        os.remove(file.path)


async def compute_hash(file: Image) -> None:
    with open(file.path, "rb") as file_to_hash:
        data = file_to_hash.read()
        file.file_hash = hashlib.md5(data).hexdigest()


async def compute_pixel_hash(file: Image) -> None:
    """
    Computes a BLAKE2b hash based on raw image pixels via pyvips.
    Ignores metadata (EXIF, etc).
    """
    try:
        preview_bytes = None
        if not is_web_format(file):
            preview_bytes = await extract_jpeg_preview(file)
            logger.info(f"Extract JPEG preview form {file.name}")

        loop = asyncio.get_running_loop()
        file.pixel_hash = await loop.run_in_executor(
            None, _compute_pixel_hash_sync, file, preview_bytes
        )
    except pyvips.Error as e:
        logger.exception(f"Error computing pixel hash for {file.path}")
        raise ImageDecodingError(
            code=ErrorCode.IMAGE_DECODING_ERROR,
            filename=file.name,
        ) from e


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
        logger.info(
            "No preview bytes or web format image for pixel hash computing, "
            f"using default solution for {image.name}"
        )

    file_hash = hashlib.blake2b(digest_size=16)

    # Process image in chunks using crop() which supports sequential streaming
    chunk_height = 512

    for y in range(0, img.height, chunk_height):
        height_to_process = min(chunk_height, img.height - y)
        data = img.crop(0, y, img.width, height_to_process).write_to_memory()
        file_hash.update(data)

    return file_hash.hexdigest()


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
            logger.info("Perceptual hash compute on extracted JPEG preview image")

        loop = asyncio.get_running_loop()
        image.perceptual_hash = await loop.run_in_executor(
            None, _compute_perceptual_hash_sync, path, preview_bytes
        )
    except pyvips.Error as e:
        logger.exception(f"Error computing perceptual hash for {image.path}")
        raise ImageProcessingError(
            code=ErrorCode.IMAGE_PROCESSING_ERROR,
            filename=image.name,
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
            except TimeoutError:
                with contextlib.suppress(OSError):
                    proc.kill()
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
        logging.warning(
            f"Image {image.name} with perceptual hash {image.perceptual_hash} already exists."
        )
        raise DuplicateImageError(
            code=ErrorCode.DUPLICATE_PERCEPTUAL_HASH,
            filename=image.name,
            perceptual_hash=image.perceptual_hash,
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
    logging.info(f"Extension finded for {image.name}: {extension}")
    storage_path = os.path.join(
        config.settings.storage_dir, image.path_hash_dir, image.path_hash_file + extension
    )
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    os.rename(image.path, storage_path)
    image.path = storage_path
    logging.info(f"File {image.name} moved to {storage_path}")


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
        logging.warning(
            f"Image {image.name} has unsupported GPS Map Datum: {gps_datum}. "
            "Only WGS-84 is supported."
        )
        raise UnsupportedGpsDatumError(
            code=ErrorCode.UNSUPPORTED_GPS_DATUM,
            filename=image.name,
            gps_datum=gps_datum,
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
        logging.warning(
            f"Image {image.name} with image unique ID {image.image_unique_id} already exists."
        )
        raise DuplicateImageError(
            code=ErrorCode.DUPLICATE_IMAGE_UNIQUE_ID,
            filename=image.name,
            image_unique_id=image.image_unique_id,
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
        logging.warning(f"dzi file not found for {image.name} at {dzi_path}")
        return None

    with ZipFile(dzi_path, "r") as zip_file:
        tile_path = f"{image.path_hash_file}/{zoom}/{x}/{y}.jpg"
        try:
            with zip_file.open(tile_path) as tile_file:
                return tile_file.read()
        except KeyError:
            logging.exception(f"Tile {tile_path} not found in dzi file {dzi_path}")
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
            logging.exception(f"Image {image.name} not found at {img_path}")
            return None
