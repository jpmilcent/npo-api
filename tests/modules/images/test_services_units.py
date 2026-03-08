import asyncio
from datetime import datetime
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
import pyvips
from tests.constants import (
    ERROR_DUPLICATE_IMAGE_UNIQUE_ID,
    ERROR_UNSUPPORTED_GPS_DATUM,
    LOG_DUPLICATE_IMAGE_UNIQUE_ID,
    MSG_UNSUPPORTED_GPS_DATUM,
)

from npo.core.constants import ErrorCode
from npo.modules.images.exceptions import (
    DuplicateImageError,
    FileTooLargeError,
    ImageDecodingError,
    ImageProcessingError,
    InsufficientStorageError,
    StorageError,
    UnsupportedGpsDatumError,
)
from npo.modules.images.schemas import Image
from npo.modules.images.services import (
    HashService,
    ImageService,
    MetadataService,
    StorageService,
)

# Define an arbitrary limit of 100 bytes for the upload size
TEST_UPLOAD_MAX_SIZE = 100
# Define an arbitrary limit of 100 bytes for the upload safety buffer
TEST_UPLOAD_SAFETY_BUFFER = 10


@patch("npo.core.config.backend_settings.max_upload_size", TEST_UPLOAD_MAX_SIZE)
def test_check_max_upload_size_success():
    """Verify that no exception is raised if the size is <= the limit."""
    storage_service = StorageService()
    # Case 1: Size is smaller
    storage_service.check_max_upload_size(50)

    # Case 2: Size is exactly equal to the limit
    storage_service.check_max_upload_size(100)


@patch("npo.core.config.backend_settings.max_upload_size", TEST_UPLOAD_MAX_SIZE)
def test_check_max_upload_size_failure():
    """Verify that an APIException is raised if the size exceeds the limit."""
    storage_service = StorageService()
    with pytest.raises(FileTooLargeError) as exc_info:
        storage_service.check_max_upload_size(101)

    assert exc_info.value.code == "FILE_TOO_LARGE"


@patch("npo.modules.images.services.shutil.disk_usage")
@patch("npo.core.config.backend_settings.upload_safety_buffer", TEST_UPLOAD_SAFETY_BUFFER)
def test_check_required_space_success(mock_disk_usage):
    """Verify that no exception is raised if there is enough disk space."""
    storage_service = StorageService()
    # Mock the image object
    mock_image = MagicMock()
    mock_image.path = "/tmp/test.jpg"

    # Case 1: Unknown size (None), free space (20) > buffer (10)
    mock_image.size = None
    mock_disk_usage.return_value = (100, 50, 20)  # total, used, free
    storage_service.check_required_space(mock_image)

    # Case 2: Known size (50), free space (60) >= buffer (10) + size (50)
    mock_image.size = 50
    mock_disk_usage.return_value = (100, 40, 60)
    storage_service.check_required_space(mock_image)


@patch("npo.modules.images.services.shutil.disk_usage")
@patch("npo.core.config.backend_settings.upload_safety_buffer", TEST_UPLOAD_SAFETY_BUFFER)
def test_check_required_space_failure(mock_disk_usage):
    """Verify that an APIException is raised if disk space is insufficient."""
    storage_service = StorageService()
    mock_image = MagicMock()
    mock_image.path = "/tmp/test.jpg"

    # Case 1: Unknown size, free space (5) < buffer (10)
    mock_image.size = None
    mock_disk_usage.return_value = (100, 95, 5)

    with pytest.raises(InsufficientStorageError) as exc_info:
        storage_service.check_required_space(mock_image)

    assert exc_info.value.code == "INSUFFICIENT_STORAGE"
    # Case 2: Known size (50), free space (59) < buffer (10) + size (50)
    mock_image.size = 50
    mock_disk_usage.return_value = (100, 41, 59)

    with pytest.raises(InsufficientStorageError) as exc_info:
        storage_service.check_required_space(mock_image)

    assert exc_info.value.code == "INSUFFICIENT_STORAGE"


async def test_save_file_os_error():
    """
    Verify that an OSError during file writing is caught and re-raised as a StorageError.
    """
    storage_service = StorageService()
    mock_upload_file = AsyncMock()
    mock_upload_file.read.side_effect = [b"chunk1", b""]
    mock_upload_file.close = AsyncMock()
    mock_image = Image(name="test.jpg", path="/fake/path/test.jpg", size=100)

    with (
        patch.object(storage_service, "check_max_upload_size"),
        patch.object(storage_service, "check_required_space"),
        patch("npo.modules.images.services.open", side_effect=OSError("Disk full")) as mock_open,
    ):
        with pytest.raises(StorageError) as exc_info:
            await storage_service.save_file(mock_upload_file, mock_image)

        assert exc_info.value.code == ErrorCode.FILE_UPLOAD_ERROR
        mock_open.assert_called_once_with(mock_image.path, "wb")
        # Verify that the file was closed even on error
        mock_upload_file.close.assert_awaited_once()


async def test_save_file_domain_error_cleanup():
    """
    Verify that if a DomainError occurs during save, the partial file is cleaned up.
    """
    storage_service = StorageService()
    mock_upload_file = AsyncMock()
    mock_upload_file.read.side_effect = [b"chunk1", b"chunk2", b""]
    mock_upload_file.close = AsyncMock()
    mock_image = Image(name="test.jpg", path="/fake/path/test.jpg", size=100)

    with (
        patch.object(storage_service, "check_max_upload_size") as mock_check_size,
        patch.object(storage_service, "check_required_space"),
        patch("npo.modules.images.services.open", MagicMock()),
        patch.object(storage_service, "clean_upload_file") as mock_clean_file,
    ):
        # Let the first check (on total size) pass, but fail the second one (on written bytes)
        mock_check_size.side_effect = [
            None,
            FileTooLargeError(code=ErrorCode.FILE_TOO_LARGE),
        ]

        with pytest.raises(FileTooLargeError):
            await storage_service.save_file(mock_upload_file, mock_image)

        # Assert that cleanup was called
        mock_clean_file.assert_called_once_with(mock_image)
        # Assert that the file was closed in the finally block
        mock_upload_file.close.assert_awaited_once()


async def test_clean_upload_file():
    """
    Verify that clean_upload_file removes the file at the given image path.
    """
    storage_service = StorageService()
    mock_image = Image(name="test.jpg", path="/fake/path/test.jpg", size=100)

    with (
        patch("os.path.exists", return_value=True),
        patch("npo.modules.images.services.os.remove") as mock_remove,
    ):
        storage_service.clean_upload_file(mock_image)
        mock_remove.assert_called_once_with(mock_image.path)


async def test_clean_upload_file_not_exists():
    """
    Verify that clean_upload_file does nothing if the file does not exist.
    """
    storage_service = StorageService()
    mock_image = Image(name="test.jpg", path="/fake/path/test.jpg", size=100)

    with (
        patch("os.path.exists", return_value=False),
        patch("npo.modules.images.services.os.remove") as mock_remove,
    ):
        storage_service.clean_upload_file(mock_image)
        mock_remove.assert_not_called()


async def test_get_file_extension_no_mime():
    """
    Test that get_file_extension returns an empty string if image.mime is None.
    """
    storage_service = StorageService()
    mock_image = MagicMock()
    mock_image.mime = None
    assert await storage_service.get_file_extension(mock_image) == ""


async def test_compute_pixel_hash_failure():
    """Verify that an ImageDecodingError is raised if pyvips fails."""
    hash_service = HashService()
    mock_image = Image(name="test.jpg", path="/fake/path/test.jpg", size=100)

    with (
        patch("npo.modules.images.services.asyncio.get_running_loop") as mock_get_loop,
        patch("npo.modules.images.services.logger") as logger,
    ):
        mock_loop = MagicMock()
        mock_get_loop.return_value = mock_loop
        mock_loop.runmock_loop = MagicMock()
        mock_get_loop.return_value = mock_loop
        mock_loop.run_in_executor = AsyncMock(side_effect=pyvips.Error("Decoding failed"))

        with pytest.raises(ImageDecodingError) as exc_info:
            await hash_service.compute_pixel_hash(mock_image)

    assert logger.exception.call_once()
    assert logger.exception.call_args[0][0] == f"Error computing pixel hash for {mock_image.path}"
    assert exc_info.value.code == ErrorCode.IMAGE_DECODING_ERROR
    assert exc_info.value.kwargs["filename"] == mock_image.name


async def test_compute_pixel_hash_sync():
    """Verify that compute_pixel_hash works in the synchronous path."""
    hash_service = HashService()
    mock_image = Image(name="test.dng", path="/fake/path/test.dng", size=100)
    mock_preview_bytes = None

    with (
        patch("npo.modules.images.services.pyvips.Image.new_from_file") as mock_new_from_file,
        patch("npo.modules.images.services.logger") as mock_logger,
    ):
        mock_vips_image = MagicMock()
        mock_vips_image.height = 512
        mock_vips_image.width = 512
        mock_vips_image.colourspace.return_value = mock_vips_image
        mock_vips_image.crop.return_value = mock_vips_image
        mock_vips_image.write_to_memory.return_value = b"pixeldata"
        mock_new_from_file.return_value = mock_vips_image

        pixel_hash = hash_service._compute_pixel_hash_sync(
            mock_image, mock_preview_bytes, is_web=False
        )

    assert mock_logger.info.call_once()
    assert mock_logger.info.call_args[0][0] == (
        "No preview bytes or web format image for pixel hash computing, "
        f"using default solution for {mock_image.name}"
    )

    expected_hash = "c237defcffb8952f758e419eb57d88c2"  # BLAKE2b 32 hexa of b"pixeldata"
    assert pixel_hash == expected_hash


async def test_compute_perceptual_hash():
    """Verify that compute_perceptual_hash returns the expected hash."""
    hash_service = HashService()
    mock_image = Image(name="test.jpg", path="/fake/path/test.jpg", size=100)

    with (
        patch("npo.modules.images.services.asyncio.get_running_loop") as mock_get_loop,
        patch("npo.modules.images.services.logger") as logger,
    ):
        mock_loop = MagicMock()
        mock_get_loop.return_value = mock_loop
        mock_loop.run_in_executor = AsyncMock(side_effect=pyvips.Error("Decoding failed"))

        with pytest.raises(ImageProcessingError) as exc_info:
            await hash_service.compute_perceptual_hash(mock_image)

        logger.exception.call_once()
        assert logger.exception.call_args[0][0] == (
            f"Error computing perceptual hash for {mock_image.path}"
        )
        assert exc_info.value.code == ErrorCode.IMAGE_PROCESSING_ERROR
        assert exc_info.value.kwargs["filename"] == mock_image.name


@pytest.fixture()
def extract_preview_fixture():
    """
    Fixture to mock dependencies for extract_jpeg_preview tests.

    It provides mocks for subprocess, wait_for, logger, and a mock image object.
    """
    storage_service = StorageService()
    mock_image = MagicMock(path="/tmp/test.jpg")

    with (
        patch("npo.modules.images.services.asyncio.create_subprocess_exec") as mock_exec,
        patch("npo.modules.images.services.asyncio.wait_for") as mock_wait_for,
        patch("npo.modules.images.services.logger") as mock_logger,
    ):
        mock_proc = AsyncMock()
        mock_proc.kill = MagicMock()
        mock_proc.communicate = MagicMock()
        mock_exec.return_value = mock_proc

        class Mocks:
            exec = mock_exec
            wait_for = mock_wait_for
            logger = mock_logger
            proc = mock_proc
            image = mock_image
            service = storage_service
            tags: ClassVar = ["-PreviewImage", "-JpgFromRaw"]

        yield Mocks


async def test_extract_jpeg_preview_timeout(extract_preview_fixture):
    """
    Verify that a TimeoutError during preview extraction kills the process and continues.
    """
    mocks = extract_preview_fixture

    # We simulate the TimeoutError raised by wait_for
    mocks.wait_for.side_effect = asyncio.TimeoutError

    result = await mocks.service.extract_jpeg_preview(mocks.image)

    assert result is None
    # The loop runs twice (for each tag), so kill must be called twice
    assert mocks.proc.kill.call_count == len(mocks.tags)


async def test_extract_jpeg_preview_timeout_kill_error(extract_preview_fixture):
    """
    Verify that OSError during process kill (inside TimeoutError handling) is suppressed.
    """
    mocks = extract_preview_fixture

    # We simulate an OSError when kill is called (e.g. process already dead)
    mocks.proc.kill.side_effect = OSError("Process already dead")
    mocks.wait_for.side_effect = asyncio.TimeoutError

    # The exception must be suppressed and not propagate
    result = await mocks.service.extract_jpeg_preview(mocks.image)

    assert result is None
    assert mocks.proc.kill.call_count == len(mocks.tags)


async def test_extract_jpeg_preview_exiftool_error(extract_preview_fixture):
    """
    Verify that an ExifTool error generates a log message.
    """
    mocks = extract_preview_fixture
    tags_tested = mocks.tags

    # Simulate a failed exiftool execution
    mocks.proc.returncode = 1
    mocks.wait_for.return_value = (b"", b"exiftool error")

    result = await mocks.service.extract_jpeg_preview(mocks.image)

    assert result is None
    # The loop runs twice, logging a warning each time
    assert mocks.logger.warning.call_count == len(mocks.tags)
    expected_calls = [
        call(f"Exiftool error for {mocks.image.path} with tag {tag}: exiftool error")
        for tag in tags_tested
    ]
    mocks.logger.warning.assert_has_calls(expected_calls)


async def test_extract_jpeg_preview_generate_exception(extract_preview_fixture):
    """
    Verify that a generic exception during subprocess creation is logged.
    """
    mocks = extract_preview_fixture
    tags_tested = mocks.tags

    error_msg = "Generic exiftool error"
    mocks.exec.side_effect = Exception(error_msg)

    result = await mocks.service.extract_jpeg_preview(mocks.image)

    assert result is None
    assert mocks.logger.warning.call_count == len(tags_tested)
    expected_calls = [
        call(f"Error extracting preview for {mocks.image.path} with tag {tag}: {error_msg}")
        for tag in tags_tested
    ]
    mocks.logger.warning.assert_has_calls(expected_calls)


@pytest.fixture()
def get_file_from_dzi_fixture():
    """
    Fixture to mock dependencies for get_file_from_dzi tests.
    """
    fake_storage_dir = "fake_storage_dir/"
    mock_img = MagicMock()
    mock_img.name = "fake_image"
    mock_img.path_hash_dir = "fake_hash_dir/"
    mock_img.path_hash_file = "fake_hash_file"
    fake_zoom = 1
    fake_x = 2
    fake_y = 3
    fake_tile_path = f"{mock_img.path_hash_file}/{fake_zoom}/{fake_x}/{fake_y}.jpg"

    with (
        patch("npo.modules.images.services.config.settings.storage_dir", fake_storage_dir),
        patch("npo.modules.images.services.os.path.exists") as mock_os_path_exists,
        patch("npo.modules.images.services.logging") as mock_logging,
        patch("npo.modules.images.services.ZipFile") as mock_zip,
    ):

        class Mocks:
            storage_dir = fake_storage_dir
            img = mock_img
            dzi_path = f"{fake_storage_dir}{mock_img.path_hash_dir}{mock_img.path_hash_file}.szi"
            zoom = fake_zoom
            x = fake_x
            y = fake_y
            tile_path = fake_tile_path
            logging = mock_logging
            os_path_exists = mock_os_path_exists
            zip = mock_zip

        yield Mocks


async def test_get_file_from_dzi_when_dzi_not_found(get_file_from_dzi_fixture):
    mocks = get_file_from_dzi_fixture
    mocks.os_path_exists.return_value = False

    result = await StorageService().get_tile_from_dzi(mocks.img, mocks.zoom, mocks.x, mocks.y)

    assert result is None
    mocks.logging.warning.assert_called_once_with(
        f"dzi file not found for {mocks.img.name} at {mocks.dzi_path}"
    )


async def test_get_file_from_dzi_when_tile_not_found(get_file_from_dzi_fixture):
    mocks = get_file_from_dzi_fixture
    mocks.os_path_exists.return_value = True
    # Simulate that zip_file.open() raises a KeyError because the tile is not found
    mocks.zip.return_value.__enter__.return_value.open.side_effect = KeyError()

    # The method should catch the KeyError, log it, and return None
    result = await StorageService().get_tile_from_dzi(mocks.img, mocks.zoom, mocks.x, mocks.y)

    assert result is None
    mocks.logging.exception.assert_called_once_with(
        f"Tile {mocks.tile_path} not found in dzi file {mocks.dzi_path}"
    )


async def test_get_image_return_preview_jpeg_bytes():
    fake_img_preview_bytes = b"some content"
    mock_img = MagicMock()
    storage_service = StorageService()

    with (
        patch.object(storage_service, "is_web_format", return_value=False) as mock_is_web,
        patch.object(
            storage_service, "extract_jpeg_preview", new_callable=AsyncMock
        ) as mock_extract,
    ):
        mock_extract.return_value = fake_img_preview_bytes

        result = await storage_service.get_image(mock_img)

    assert result == fake_img_preview_bytes
    mock_is_web.assert_called_once_with(mock_img)
    mock_extract.assert_awaited_once_with(mock_img)


async def test_get_image_file_not_found():
    mock_img = MagicMock()
    mock_img.path_hash_dir = "fake_hash_dir"
    mock_img.path_hash_file = "fake_hash_file"
    storage_service = StorageService()

    with (
        patch("npo.modules.images.services.config.settings.storage_dir", "fake_storage_dir"),
        patch.object(storage_service, "get_file_extension", new_callable=AsyncMock) as mock_get_ext,
        patch("npo.modules.images.services.open") as mock_open,
        patch("npo.modules.images.services.logging") as mock_logging,
    ):
        mock_get_ext.return_value = "jpg"
        mock_open.side_effect = FileNotFoundError()

        result = await storage_service.get_image(mock_img)

    assert result is None
    assert mock_logging.exception.call_once()


def test_compute_perceptual_hash_sync_no_source():
    """
    Verify that _compute_perceptual_hash_sync raises pyvips.Error
    when neither path nor data is provided.
    """
    hash_service = HashService()
    with pytest.raises(pyvips.Error) as exc_info:
        hash_service._compute_perceptual_hash_sync(path=None, data=None)

    assert str(exc_info.value).strip() == "No image source available for perceptual hash"


def test_check_gps_map_datum_not_wgs84():
    mock_image = MagicMock()
    mock_image.name = "test.jpg"
    datum = "not_wgs84"
    mock_metadata = {"EXIF:GPSMapDatum": datum}
    with (
        patch("npo.modules.images.services.logging") as mock_logging,
        pytest.raises(UnsupportedGpsDatumError) as exc_info,
    ):
        MetadataService().check_gps_map_datum(mock_image, mock_metadata)

    assert exc_info.value.code == ERROR_UNSUPPORTED_GPS_DATUM
    mock_logging.warning.assert_called_once_with(
        MSG_UNSUPPORTED_GPS_DATUM.format(filename=mock_image.name, gps_datum=datum)
    )


@pytest.mark.parametrize(
    ("alt", "ref", "expected_value"),
    [
        (1100, 1, -1100),
        (1100, 0, 1100),
    ],
)
def test_extract_metadata_altitude_success(alt, ref, expected_value):
    mock_metadata = {"EXIF:GPSAltitude": alt, "EXIF:GPSAltitudeRef": ref}
    result = MetadataService().extract_metadata_altitude(mock_metadata)
    assert result == expected_value


@pytest.mark.parametrize(
    ("lat", "ref", "expected_value"),
    [
        (45.8, "S", -45.8),
        (45.8, "N", 45.8),
    ],
)
def test_extract_metadata_latitude_success(lat, ref, expected_value):
    mock_metadata = {"EXIF:GPSLatitude": lat, "EXIF:GPSLatitudeRef": ref}
    result = MetadataService().extract_metadata_latitude(mock_metadata)
    assert result == expected_value


@pytest.mark.parametrize(
    ("lon", "ref", "expected_value"),
    [
        (5.3, "W", -5.3),
        (5.3, "E", 5.3),
    ],
)
def test_extract_metadata_longitude_success(lon, ref, expected_value):
    mock_metadata = {"EXIF:GPSLongitude": lon, "EXIF:GPSLongitudeRef": ref}
    result = MetadataService().extract_metadata_longitude(mock_metadata)
    assert result == expected_value


def test_parse_exif_date_success():
    fake_date = "2026:03:08 13:43:15"

    result = MetadataService().parse_exif_date(fake_date)

    assert result == datetime(2026, 3, 8, 13, 43, 15)


@pytest.mark.parametrize(
    ("fake_date"),
    [
        ("not_a_date"),
        ("2026-03-08 13:43:15"),
    ],
)
def test_parse_exif_date_with_value_error(fake_date):
    fake_date = "fake_date"

    result = MetadataService().parse_exif_date(fake_date)

    assert result is None


async def test_check_duplicates_by_image_unique_id():
    mock_db = AsyncMock()
    mock_image_storage = MagicMock()
    mock_image = MagicMock()
    mock_image.name = "test.jpg"
    mock_image.image_unique_id = "fake_image_unique_id"
    with (
        patch(
            "npo.modules.images.services.get_image_by_image_unique_id", new_callable=AsyncMock
        ) as mock_get_by_id,
        patch("npo.modules.images.services.logging") as mock_logging,
    ):
        mock_get_by_id.return_value = mock_image_storage
        with pytest.raises(DuplicateImageError) as exc_info:
            await ImageService(mock_db).check_duplicates_by_image_unique_id(mock_image)

    mock_logging.warning.assert_called_once_with(
        LOG_DUPLICATE_IMAGE_UNIQUE_ID.format(
            image_name=mock_image.name, image_unique_id=mock_image.image_unique_id
        )
    )
    assert exc_info.value.code == ERROR_DUPLICATE_IMAGE_UNIQUE_ID
    assert exc_info.value.kwargs["filename"] == mock_image.name
    assert exc_info.value.kwargs["image_unique_id"] == mock_image.image_unique_id


async def test_store_image_infos_update_existing():
    """
    Verify that store_image_infos updates an existing image record
    instead of creating a new one.
    """
    mock_db = AsyncMock()

    # The existing image in the database (mock)
    mock_storage_image = MagicMock()
    mock_storage_image.name = "old_name.jpg"
    mock_storage_image.size = 50

    # The new image data coming from the service processing
    fake_size = 100
    new_image_data = Image(
        name="new_name.jpg",
        path="/tmp/new_path.jpg",
        pixel_hash="pixel_hash_123",
        file_hash="file_hash_123",
        size=fake_size,
        mime="image/png",
        user_id=1,
    )

    with patch(
        "npo.modules.images.services.get_image_by_pixel_hash", new_callable=AsyncMock
    ) as mock_get_by_hash:
        mock_get_by_hash.return_value = mock_storage_image

        service = ImageService(mock_db)
        await service.store_image_infos(new_image_data)

    # Verify attributes on the storage object were updated
    assert mock_storage_image.name == "new_name.jpg"
    assert mock_storage_image.path == "/tmp/new_path.jpg"
    assert mock_storage_image.size == fake_size
    assert mock_storage_image.mime == "image/png"

    # Verify db interactions
    mock_db.add.assert_not_called()
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once_with(mock_storage_image)
