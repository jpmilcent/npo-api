from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Response, status
from tests.constants import (
    ERROR_FILE_TOO_LARGE,
    ERROR_IMAGE_DECODING_ERROR,
    ERROR_IMAGE_DZI_NOT_FOUND,
    ERROR_INSUFFICIENT_STORAGE,
)

from npo.core.constants import ErrorCode
from npo.core.exceptions import APIException
from npo.modules.images.exceptions import (
    FileTooLargeError,
    ImageDecodingError,
    InsufficientStorageError,
)
from npo.modules.images.routes import (
    delete_image,
    get_image_full,
    get_image_tile,
    get_photography_metadata,
    get_raw_metadata,
)


async def test_root_pagination(client):
    """
    Test the pagination logic of the root endpoint.
    """
    # Mock get_images_list to return specific totals without needing DB entries
    with patch("npo.modules.images.routes.get_images_list", new_callable=AsyncMock) as mock_get:
        # Case 1: Total items > limit (multiple pages)
        # 150 items, limit 50 -> 3 pages
        TOTAL_ITEMS_1 = 150
        ITEMS_PER_PAGE = 50
        TOTAL_PAGES_1 = 3
        mock_get.return_value = ([], TOTAL_ITEMS_1)

        response = await client.get("/images/?page=1&size=50")
        assert response.status_code == status.HTTP_200_OK
        pagination = response.json()["meta"]["pagination"]

        assert pagination["total_items"] == TOTAL_ITEMS_1
        assert pagination["total_pages"] == TOTAL_PAGES_1
        assert pagination["items_per_page"] == ITEMS_PER_PAGE

        # Case 2: Total items < limit (1 page)
        TOTAL_ITEMS_2 = 10
        TOTAL_PAGES_2 = 1
        mock_get.return_value = ([], TOTAL_ITEMS_2)

        response = await client.get("/images/?page=1&size=50")
        assert response.status_code == status.HTTP_200_OK
        pagination = response.json()["meta"]["pagination"]

        assert pagination["total_items"] == TOTAL_ITEMS_2
        assert pagination["total_pages"] == TOTAL_PAGES_2


async def test_get_tiles_units(client):
    with patch(
        "npo.modules.images.dependencies.get_image_for_user", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None

        # This test requires an authenticated user, which the `client` fixture provides.
        pixel_hash = "abcdef1234567890abcdef1234567890"
        zoom = 2
        x = 0
        y = 1
        response = await client.get(f"/images/{pixel_hash}/{zoom}/{x}/{y}.jpg")
        assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_image_tile_success():
    """
    Check that get_image_tile returns a Response with binary content
    when the image and tile are found.
    """
    zoom, x, y = 1, 0, 0
    fake_tile_content = b"\xff\xd8\xff\xe0"  # JPEG partial signature

    mock_db = AsyncMock()
    mock_image_storage = MagicMock()

    with patch("npo.modules.images.routes.ImageService") as MockImageService:
        mock_service_instance = MockImageService.return_value
        mock_service_instance.storage_service.get_tile_from_dzi = AsyncMock(
            return_value=fake_tile_content
        )

        response = await get_image_tile(mock_image_storage, zoom, x, y, mock_db)

        assert isinstance(response, Response)
        assert response.body == fake_tile_content
        assert response.media_type == "image/jpeg"

        mock_service_instance.storage_service.get_tile_from_dzi.assert_awaited_once_with(
            mock_image_storage, zoom, x, y
        )


async def test_get_image_tile_not_exists():
    """
    Check the response when get_image_tile not found the image file inside DZI archive.
    """
    pixel_hash = "test_hash_123"
    zoom, x, y = 1, 0, 0

    mock_db = AsyncMock()
    mock_image_storage = MagicMock()
    mock_image_storage.pixel_hash = pixel_hash

    with (
        patch("npo.modules.images.routes.ImageService") as MockImageService,
    ):
        mock_service_instance = MockImageService.return_value
        mock_service_instance.storage_service.get_tile_from_dzi = AsyncMock(return_value=None)

        with pytest.raises(APIException) as exc_info:
            await get_image_tile(mock_image_storage, zoom, x, y, mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail["code"] == ERROR_IMAGE_DZI_NOT_FOUND
        assert (
            exc_info.value.detail["message"]
            == f"DZI tile for image {pixel_hash} tile {zoom}/{x}/{y} not found."
        )

        mock_service_instance.storage_service.get_tile_from_dzi.assert_awaited_once_with(
            mock_image_storage, zoom, x, y
        )


async def test_get_image_full():
    """
    Check that get_image_full returns a Response with binary content
    when the image is found.
    """
    fake_image_content = b"\xff\xd8\xff\xe0"  # JPEG partial signature

    mock_db = AsyncMock()
    mock_image_storage = MagicMock()

    with patch("npo.modules.images.routes.ImageService") as MockImageService:
        mock_service_instance = MockImageService.return_value
        mock_service_instance.storage_service.get_image = AsyncMock(return_value=fake_image_content)
        mock_service_instance.storage_service.is_web_format.return_value = (
            False  # Force JPEG response
        )

        response = await get_image_full(mock_image_storage, mock_db)

        assert isinstance(response, Response)
        assert response.body == fake_image_content
        assert response.media_type == "image/jpeg"

        mock_service_instance.storage_service.get_image.assert_awaited_once_with(mock_image_storage)
        mock_service_instance.storage_service.is_web_format.assert_called_once_with(
            mock_image_storage
        )


async def test_get_raw_metadata_success():
    """
    Test that get_raw_metadata returns the correct metadata when found.
    """
    pixel_hash = "test_hash_123"
    expected_metadata = {"camera": "TestCam", "exposure": "1/100s"}

    mock_file_storage = MagicMock()
    mock_file_storage.meta_data = expected_metadata
    mock_file_storage.pixel_hash = pixel_hash

    metadata = await get_raw_metadata(mock_file_storage)

    assert metadata == expected_metadata


@patch("npo.modules.images.metadata_formatters._", new=lambda x: x)
async def test_get_metadata_photography_success():
    """
    Test that get_photography_metadata returns the correct metadata when found.
    """
    metadata = {
        "EXIF:Make": "TestMake",
        "EXIF:Model": "TestModel",
        "EXIF:LensModel": "TestLens",
        "EXIF:FocalLength": 50.0,
        "EXIF:FocalLengthIn35mmFormat": 50.0,
        "EXIF:FNumber": 13,
        "EXIF:ISO": 100,
        "EXIF:ExposureTime": 0.0003333333333,
        "EXIF:Flash": 0,
        "EXIF:ColorSpace": 2,
        "EXIF:ExposureCompensation": 1.5,
        "EXIF:ExposureMode": 1,
        "EXIF:ExposureProgram": 5,
        "File:ImageHeight": 1282,
        "File:ImageWidth": 1920,
        "EXIF:MeteringMode": 5,
        "EXIF:Orientation": 6,
        "EXIF:SceneCaptureType": 0,
        "EXIF:SceneType": 1,
        "EXIF:WhiteBalance": 0,
    }
    expected_metadata = {
        "cameraMaker": "TestMake",
        "cameraModel": "TestModel",
        "lensModel": "TestLens",
        "focalLength": "50 mm",
        "focalLengthIn35mmFormat": "50 mm",
        "aperture": "f/13",
        "shutterSpeed": "1/3000",
        "iso": 100,
        "flash": "No Flash",
        "colorSpace": "Adobe RGB",
        "exposureCompensation": "+1.5 EV",
        "exposureMode": "Manual",
        "exposureProgram": "Creative program",
        "imageHeight": "1282 px",
        "imageWidth": "1920 px",
        "meteringMode": "Pattern",
        "orientation": "Rotate 90 CW",
        "sceneCaptureType": "Standard",
        "sceneType": "Directly photographed",
        "whiteBalance": "Auto",
    }
    mock_db = AsyncMock()
    mock_file_storage = MagicMock()
    mock_file_storage.meta_data = metadata

    result = await get_photography_metadata(mock_file_storage, mock_db)

    assert result == expected_metadata


async def test_delete_image():
    """
    Test that delete_image calls db.delete and db.commit.
    """
    mock_db = AsyncMock()
    mock_file_storage = MagicMock()

    await delete_image(mock_file_storage, mock_db)

    mock_db.delete.assert_awaited_once_with(mock_file_storage)
    mock_db.commit.assert_awaited_once()


async def test_upload_image_file_too_large(client):
    """
    Test that uploading a file that is too large returns a 413 error.
    """
    with patch("npo.modules.images.routes.ImageService") as MockImageService:
        mock_instance = MockImageService.return_value
        mock_instance.process_upload.side_effect = FileTooLargeError(code=ErrorCode.FILE_TOO_LARGE)

        files = {"files": ("test.jpg", b"some content", "image/jpeg")}
        response = await client.post("/images/upload", files=files)

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    response_data = response.json()
    assert "detail" in response_data
    error_detail = response_data["detail"]
    assert error_detail["code"] == ERROR_FILE_TOO_LARGE
    assert "message" in error_detail


async def test_upload_image_insufficient_storage(client):
    """
    Test that uploading a file with insufficient storage returns a 507 error.
    """
    with patch("npo.modules.images.routes.ImageService") as MockImageService:
        mock_instance = MockImageService.return_value
        mock_instance.process_upload.side_effect = InsufficientStorageError(
            code=ErrorCode.INSUFFICIENT_STORAGE
        )

        files = {"files": ("test.jpg", b"some content", "image/jpeg")}
        response = await client.post("/images/upload", files=files)

    assert response.status_code == status.HTTP_507_INSUFFICIENT_STORAGE
    response_data = response.json()
    assert "detail" in response_data
    error_detail = response_data["detail"]
    assert error_detail["code"] == ERROR_INSUFFICIENT_STORAGE
    assert "message" in error_detail


async def test_upload_image_decoding_error(client):
    """
    Test that a processing error during upload returns a 400 error.
    """
    with patch("npo.modules.images.routes.ImageService") as MockImageService:
        mock_instance = MockImageService.return_value
        mock_instance.process_upload.side_effect = ImageDecodingError(
            code=ErrorCode.IMAGE_DECODING_ERROR, filename="test.jpg"
        )

        files = {"files": ("test.jpg", b"some content", "image/jpeg")}
        response = await client.post("/images/upload", files=files)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    response_data = response.json()
    assert "detail" in response_data
    error_detail = response_data["detail"]
    assert error_detail["code"] == ERROR_IMAGE_DECODING_ERROR
    assert "message" in error_detail
