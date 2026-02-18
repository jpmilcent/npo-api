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
from npo.core.exceptions import DomainError
from npo.modules.images.crud import (
    get_image_by_image_unique_id,
    get_image_by_perceptual_hash,
    get_image_by_pixel_hash,
)
from npo.modules.images.exceptions import (
    DuplicateImageError,
    FileTooLargeError,
    ImageDecodingError,
    ImageProcessingError,
    InsufficientStorageError,
    StorageError,
    UnsupportedGpsDatumError,
)
from npo.modules.images.models import Image as ImageStorage
from npo.modules.images.schemas import Image
from npo.modules.users.models import User

logger = logging.getLogger(__name__)


class StorageService:
    def check_max_upload_size(self, file_size: int) -> None:
        """Check if the file size exceeds the maximum allowed limit (content-length)."""
        if file_size > config.backend_settings.max_upload_size:
            logger.error("File size exceeds the maximum allowed limit.")
            raise FileTooLargeError(
                code=ErrorCode.FILE_TOO_LARGE,
            )

    def check_required_space(self, file: Image) -> None:
        _total, _used, free = shutil.disk_usage(os.path.dirname(file.path))
        required_space = config.backend_settings.upload_safety_buffer
        if file.size:
            required_space += file.size

        if free < required_space:
            logger.error(f"Not enough disk space ({free} bytes) to save the file.")
            raise InsufficientStorageError(
                code=ErrorCode.INSUFFICIENT_STORAGE,
            )

    def clean_upload_file(self, file: Image) -> None:
        if os.path.exists(file.path):
            os.remove(file.path)

    async def save_file(self, upload_file: UploadFile, file: Image) -> None:
        if file.size:
            self.check_max_upload_size(file.size)

        self.check_required_space(file)

        try:
            with open(file.path, "wb") as buffer:
                written_bytes = 0
                while True:
                    chunk = await upload_file.read(1024)
                    if not chunk:
                        break
                    written_bytes += len(chunk)
                    self.check_max_upload_size(written_bytes)
                    buffer.write(chunk)
        except OSError as e:
            logger.exception(f"There was an error uploading the file {file.name}")
            raise StorageError(
                code=ErrorCode.FILE_UPLOAD_ERROR,
            ) from e
        except DomainError:
            self.clean_upload_file(file)
            raise
        finally:
            await upload_file.close()

    async def move_file(self, image: Image) -> None:
        extension = await self.get_file_extension(image)
        logging.info(f"Extension finded for {image.name}: {extension}")
        storage_path = os.path.join(
            config.settings.storage_dir, image.path_hash_dir, image.path_hash_file + extension
        )
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        os.rename(image.path, storage_path)
        image.path = storage_path
        logging.info(f"File {image.name} moved to {storage_path}")

    async def get_file_extension(self, image: Image | ImageStorage) -> str:
        if not image.mime:
            return ""
        extension = mimetypes.guess_extension(image.mime)
        if extension is None and image.mime.lower() == "image/x-adobe-dng":
            extension = ".dng"
        return extension if extension else ""

    def is_web_format(self, image: Image | ImageStorage) -> bool:
        web_format = (image.mime in ["image/jpeg", "image/png", "image/gif", "image/webp"]) or (
            image.name and image.name.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
        )
        return web_format if (web_format is not None and web_format != "") else False

    async def extract_jpeg_preview(self, image: Image | ImageStorage) -> bytes | None:
        preview_bytes = None
        # First try PreviewImage, then JpgFromRaw if the first one fails
        for tag in ["-PreviewImage", "-JpgFromRaw"]:
            try:
                # Binary extraction (-b) of the tag via exiftool
                # Use asyncio to avoid blocking the event loop
                proc = await asyncio.create_subprocess_exec(
                    "exiftool",
                    "-b",
                    tag,
                    image.path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    limit=1024 * 1024 * 50,  # Increase buffer (50 MB) for large images
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

    async def create_dzi(self, image: Image, preview_bytes: bytes | None = None) -> None:
        web_format = self.is_web_format(image)
        img = None
        if not web_format and preview_bytes:
            img = pyvips.Image.new_from_buffer(preview_bytes, "")
        elif web_format:
            img = pyvips.Image.new_from_file(image.path)

        if img:
            img = img.autorot()
            dzi_path = (
                config.settings.storage_dir + image.path_hash_dir + image.path_hash_file + ".szi"
            )
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

    async def get_tile_from_dzi(
        self, image: ImageStorage, zoom: int, x: int, y: int
    ) -> bytes | None:
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

    async def get_image(self, image: ImageStorage) -> bytes | None:
        web_format = self.is_web_format(image)
        if not web_format:
            return await self.extract_jpeg_preview(image)
        else:
            try:
                extension = await self.get_file_extension(image)
                img_path = (
                    config.settings.storage_dir
                    + image.path_hash_dir
                    + image.path_hash_file
                    + extension
                )
                with open(img_path, "rb") as img_file:
                    return img_file.read()
            except FileNotFoundError:
                logging.exception(f"Image {image.name} not found at {img_path}")
                return None


class HashService:
    async def compute_hash(self, file: Image) -> None:
        with open(file.path, "rb") as file_to_hash:
            data = file_to_hash.read()
            file.file_hash = hashlib.md5(data).hexdigest()

    async def compute_pixel_hash(self, file: Image, preview_bytes: bytes | None = None) -> None:
        """
        Computes a BLAKE2b hash based on raw image pixels via pyvips.
        Ignores metadata (EXIF, etc).
        """
        try:
            is_web = (file.mime in ["image/jpeg", "image/png", "image/gif", "image/webp"]) or (
                file.name and file.name.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
            )

            loop = asyncio.get_running_loop()
            file.pixel_hash = await loop.run_in_executor(
                None, self._compute_pixel_hash_sync, file, preview_bytes, bool(is_web)
            )
        except pyvips.Error as e:
            logger.exception(f"Error computing pixel hash for {file.path}")
            raise ImageDecodingError(
                code=ErrorCode.IMAGE_DECODING_ERROR,
                filename=file.name,
            ) from e

    def _compute_pixel_hash_sync(
        self, image: Image, preview_bytes: bytes | None, is_web: bool
    ) -> str:
        # For RAW/DNG, we must force demosaicing (development) to get the actual visual content.
        # Converting to sRGB ensures the RAW data is developed into visible pixels.
        if preview_bytes:
            img = pyvips.Image.new_from_buffer(preview_bytes, "")
        elif is_web:
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

    async def compute_perceptual_hash(
        self, image: Image, preview_bytes: bytes | None = None
    ) -> None:
        """
        Computes a perceptual hash (dHash) using pyvips.
        Resistant to resizing and compression.
        """
        try:
            is_web = (image.mime in ["image/jpeg", "image/png", "image/gif", "image/webp"]) or (
                image.name
                and image.name.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
            )

            path = None
            if is_web:
                path = image.path
            else:
                logger.info("Perceptual hash compute on extracted JPEG preview image")

            loop = asyncio.get_running_loop()
            image.perceptual_hash = await loop.run_in_executor(
                None, self._compute_perceptual_hash_sync, path, preview_bytes
            )
        except pyvips.Error as e:
            logger.exception(f"Error computing perceptual hash for {image.path}")
            raise ImageProcessingError(
                code=ErrorCode.IMAGE_PROCESSING_ERROR,
                filename=image.name,
            ) from e

    def _compute_perceptual_hash_sync(self, path: str | None, data: bytes | None) -> str:
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

    async def compute_hash_pathes(self, image: Image) -> None:
        step: int = config.settings.hash_dir_step
        chunks = [image.pixel_hash[i : i + step] for i in range(0, len(image.pixel_hash), step)]

        for part, chunk in enumerate(chunks):
            if part < config.settings.hash_dir_parts_count:
                image.path_hash_dir += chunk + "/"
            else:
                image.path_hash_file += chunk


class MetadataService:
    async def extract_mime_type(self, file: UploadFile) -> str:
        content_sample = await file.read(2048)
        mime_type = magic.from_buffer(content_sample, mime=True)

        # Since DNG is often interpreted as TIFF, magic function may return "image/tiff".
        # We correct this if extension is explicit.fix
        if mime_type == "image/tiff" and file.filename and file.filename.lower().endswith(".dng"):
            logger.info(
                f"Correcting MIME type for {file.filename} from {mime_type} to image/x-adobe-dng"
            )
            mime_type = "image/x-adobe-dng"

        await file.seek(0)
        return mime_type

    async def extract_metadata(self, image: Image) -> None:
        with exiftool.ExifToolHelper() as et:
            metadata = et.get_metadata(image.path, params=["-n"])
            for item in metadata:
                image.meta_data = item
                image.orientation = item.get("EXIF:Orientation")
                image.image_unique_id = item.get("EXIF:ImageUniqueID")

                # GPS Data
                self.check_gps_map_datum(image, item)
                image.latitude = self.extract_metadata_latitude(item)
                image.longitude = self.extract_metadata_longitude(item)
                image.altitude = self.extract_metadata_altitude(item)

                # DateTime Data
                image.datetime_shooting = self.parse_exif_date(item.get("EXIF:DateTimeOriginal"))
                image.datetime_digitized = self.parse_exif_date(item.get("EXIF:DateTimeDigitized"))

    def check_gps_map_datum(self, image: Image, metadata: dict) -> None:
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

    def extract_metadata_altitude(self, metadata: dict) -> float | None:
        altitude = metadata.get("EXIF:GPSAltitude")
        if altitude is not None and metadata.get("EXIF:GPSAltitudeRef") == 1:
            return -1.0 * altitude
        return altitude

    def extract_metadata_latitude(self, metadata: dict) -> float | None:
        latitude = metadata.get("EXIF:GPSLatitude")
        # If the reference is "S" (South), the latitude is negative
        if latitude is not None and metadata.get("EXIF:GPSLatitudeRef") == "S":
            return -1.0 * latitude
        return latitude

    def extract_metadata_longitude(self, metadata: dict) -> float | None:
        longitude = metadata.get("EXIF:GPSLongitude")
        # If the reference is "W" (West), the longitude is negative
        if longitude is not None and metadata.get("EXIF:GPSLongitudeRef") == "W":
            return -1.0 * longitude
        return longitude

    def parse_exif_date(self, date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            return None


class ImageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage_service = StorageService()
        self.hash_service = HashService()
        self.metadata_service = MetadataService()

    async def build_image_infos(self, upload_file: UploadFile, user_id: int) -> Image:
        mime_type = await self.metadata_service.extract_mime_type(upload_file)
        file_name = upload_file.filename if upload_file.filename else "unknown"

        return Image(
            name=file_name,
            path=os.path.join(config.settings.uploads_dir, file_name),
            size=upload_file.size,
            mime=mime_type,
            user_id=user_id,
        )

    async def check_duplicates_by_perceptual_hash(self, image: Image) -> None:
        if await get_image_by_perceptual_hash(image.perceptual_hash, self.db):
            logging.warning(
                f"Image {image.name} with perceptual hash {image.perceptual_hash} already exists."
            )
            raise DuplicateImageError(
                code=ErrorCode.DUPLICATE_PERCEPTUAL_HASH,
                filename=image.name,
                perceptual_hash=image.perceptual_hash,
            )

    async def check_duplicates_by_image_unique_id(self, image: Image) -> None:
        if await get_image_by_image_unique_id(image.image_unique_id, self.db):
            logging.warning(
                f"Image {image.name} with image unique ID {image.image_unique_id} already exists."
            )
            raise DuplicateImageError(
                code=ErrorCode.DUPLICATE_IMAGE_UNIQUE_ID,
                filename=image.name,
                image_unique_id=image.image_unique_id,
            )

    async def store_image_infos(self, image: Image) -> None:
        file_storage = await get_image_by_pixel_hash(image.pixel_hash, self.db)

        if file_storage:
            data = image.model_dump(exclude_none=True)
            data.pop("id", None)
            for key, value in data.items():
                setattr(file_storage, key, value)
        else:
            file_storage = ImageStorage(**image.__dict__)
            self.db.add(file_storage)

        await self.db.commit()
        await self.db.refresh(file_storage)

    async def process_upload(self, upload_file: UploadFile, user: User) -> Image:
        file = await self.build_image_infos(upload_file, user.id)

        try:
            await self.storage_service.save_file(upload_file, file)

            # Extract preview if needed (shared between hash and storage services)
            preview_bytes = None
            if not self.storage_service.is_web_format(file):
                preview_bytes = await self.storage_service.extract_jpeg_preview(file)

            await self.hash_service.compute_perceptual_hash(file, preview_bytes)
            await self.check_duplicates_by_perceptual_hash(file)
            await self.metadata_service.extract_metadata(file)
            await self.check_duplicates_by_image_unique_id(file)

            await self.hash_service.compute_hash(file)
            await self.hash_service.compute_pixel_hash(file, preview_bytes)
            await self.hash_service.compute_hash_pathes(file)
            await self.storage_service.move_file(file)
            await self.store_image_infos(file)
            await self.storage_service.create_dzi(file, preview_bytes)
        except DomainError:
            # Cleanup is handled in save_file for upload errors.
            # For other errors, we might want to clean up if we want to be strict,
            # but usually save_file handles the temporary file cleanup.
            # If we threw after save_file, the file might remain in uploads/ or partially moved.
            # In the original code, only save_file had a try/catch/finally with clean_upload_file.
            # clean_upload_file is now in StorageService.
            # If we want to clean up on ANY error:
            # if os.path.exists(file.path):
            #    self.storage_service.clean_upload_file(file)
            # But let's stick to original behavior where save_file handles its own cleanup.
            raise

        logger.info(f"File {file.name} was uploaded successfully!")
        return file
