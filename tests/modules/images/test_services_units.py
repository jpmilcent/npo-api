from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pyvips

from npo.core.constants import ErrorCode
from npo.modules.images.exceptions import (
    FileTooLargeError,
    ImageDecodingError,
    ImageProcessingError,
    InsufficientStorageError,
    StorageError,
)
from npo.modules.images.schemas import Image
from npo.modules.images.services import (
    HashService,
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
