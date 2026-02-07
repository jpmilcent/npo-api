from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Response, status
from tests.constants import (
    ERROR_FILE_TOO_LARGE,
    ERROR_IMAGE_DECODING_ERROR,
    ERROR_IMAGE_DZI_NOT_FOUND,
    ERROR_IMAGE_NOT_FOUND,
    ERROR_INSUFFICIENT_STORAGE,
    ERROR_PHOTOGRAPHY_METADATA_NOT_FOUND,
    ERROR_RAW_METADATA_NOT_FOUND,
)

from npo.core.constants import ErrorCode
from npo.core.exceptions import APIException
from npo.modules.images.exceptions import (
    FileTooLargeError,
    ImageDecodingError,
    InsufficientStorageError,
)
from npo.modules.images.routes import (
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
        "npo.modules.images.routes.get_image_by_pixel_hash", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None

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
    pixel_hash = "test_hash_123"
    zoom, x, y = 1, 0, 0
    fake_tile_content = b"\xff\xd8\xff\xe0"  # JPEG partial signature

    mock_db = AsyncMock()
    mock_image_storage = MagicMock()

    with (
        patch(
            "npo.modules.images.routes.get_image_by_pixel_hash", new_callable=AsyncMock
        ) as mock_get_img,
        patch("npo.modules.images.routes.ImageService") as MockImageService,
    ):
        mock_get_img.return_value = mock_image_storage
        mock_service_instance = MockImageService.return_value
        mock_service_instance.storage_service.get_tile_from_dzi = AsyncMock(
            return_value=fake_tile_content
        )

        response = await get_image_tile(pixel_hash, zoom, x, y, mock_db)

        assert isinstance(response, Response)
        assert response.body == fake_tile_content
        assert response.media_type == "image/jpeg"

        mock_get_img.assert_awaited_once_with(pixel_hash, mock_db)
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

    with (
        patch(
            "npo.modules.images.routes.get_image_by_pixel_hash", new_callable=AsyncMock
        ) as mock_get_img,
        patch("npo.modules.images.routes.ImageService") as MockImageService,
    ):
        mock_get_img.return_value = mock_image_storage
        mock_service_instance = MockImageService.return_value
        mock_service_instance.storage_service.get_tile_from_dzi = AsyncMock(return_value=None)

        with pytest.raises(APIException) as exc_info:
            await get_image_tile(pixel_hash, zoom, x, y, mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail["code"] == ERROR_IMAGE_DZI_NOT_FOUND
        assert (
            exc_info.value.detail["message"]
            == f"DZI tile for image {pixel_hash} tile {zoom}/{x}/{y} not found."
        )

        mock_get_img.assert_awaited_once_with(pixel_hash, mock_db)
        mock_service_instance.storage_service.get_tile_from_dzi.assert_awaited_once_with(
            mock_image_storage, zoom, x, y
        )


async def test_get_image_tile_not_found():
    """
    Check the response when get_image_tile not found image infos in database.
    """
    pixel_hash = "test_hash_123"
    zoom, x, y = 1, 0, 0

    mock_db = AsyncMock()

    with (
        patch(
            "npo.modules.images.routes.get_image_by_pixel_hash", new_callable=AsyncMock
        ) as mock_get_img,
        patch("npo.modules.images.routes.ImageService") as MockImageService,
    ):
        mock_get_img.return_value = None
        mock_service_instance = MockImageService.return_value
        # Ensure method is not called (though ImageService instantiation happens after check)
        # In current route impl, ImageService is instantiated but method called only if file found.

        with pytest.raises(APIException) as exc_info:
            await get_image_tile(pixel_hash, zoom, x, y, mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail["code"] == ERROR_IMAGE_NOT_FOUND
        assert exc_info.value.detail["message"] == f"Image {pixel_hash} not found."

        mock_get_img.assert_awaited_once_with(pixel_hash, mock_db)
        mock_service_instance.storage_service.get_tile_from_dzi.assert_not_called()


async def test_get_image_full():
    """
    Check that get_image_full returns a Response with binary content
    when the image is found.
    """
    pixel_hash = "test_hash_123"
    fake_image_content = b"\xff\xd8\xff\xe0"  # JPEG partial signature

    mock_db = AsyncMock()
    mock_image_storage = MagicMock()

    with (
        patch(
            "npo.modules.images.routes.get_image_by_pixel_hash", new_callable=AsyncMock
        ) as mock_get_image_infos,
        patch("npo.modules.images.routes.ImageService") as MockImageService,
    ):
        mock_get_image_infos.return_value = mock_image_storage
        mock_service_instance = MockImageService.return_value
        mock_service_instance.storage_service.get_image = AsyncMock(return_value=fake_image_content)
        mock_service_instance.storage_service.is_web_format.return_value = (
            False  # Force JPEG response
        )

        response = await get_image_full(pixel_hash, mock_db)

        assert isinstance(response, Response)
        assert response.body == fake_image_content
        assert response.media_type == "image/jpeg"

        mock_get_image_infos.assert_awaited_once_with(pixel_hash, mock_db)
        mock_service_instance.storage_service.get_image.assert_awaited_once_with(mock_image_storage)
        mock_service_instance.storage_service.is_web_format.assert_called_once_with(
            mock_image_storage
        )


async def test_get_image_full_not_found():
    """
    Check the response when get_image_full not found image infos in database.
    """
    pixel_hash = "test_hash_123"

    mock_db = AsyncMock()

    with patch(
        "npo.modules.images.routes.get_image_by_pixel_hash", new_callable=AsyncMock
    ) as mock_get_image_infos:
        mock_get_image_infos.return_value = None

        with pytest.raises(APIException) as exc_info:
            await get_image_full(pixel_hash, mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail["code"] == ERROR_IMAGE_NOT_FOUND
        assert exc_info.value.detail["message"] == f"Image {pixel_hash} not found."

        mock_get_image_infos.assert_awaited_once_with(pixel_hash, mock_db)


async def test_get_raw_metadata_not_found():
    """
    Test that ValueError is raised when a required argument is missing.
    """
    pixel_hash = "test_hash_123"

    mock_db = AsyncMock()
    mock_image_storage = MagicMock()
    mock_image_storage.meta_data = None
    with patch(
        "npo.modules.images.routes.get_image_by_pixel_hash", new_callable=AsyncMock
    ) as mock_get_image_infos:
        mock_get_image_infos.return_value = None

        with pytest.raises(APIException) as exc_info:
            await get_raw_metadata(pixel_hash, mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail["code"] == ERROR_RAW_METADATA_NOT_FOUND
        assert exc_info.value.detail["message"] == f"Raw metadata for file {pixel_hash} not found."

        mock_get_image_infos.assert_awaited_once_with(pixel_hash, mock_db)


async def test_get_raw_metadata_success():
    """
    Test that get_raw_metadata returns the correct metadata when found.
    """
    pixel_hash = "test_hash_123"
    expected_metadata = {"camera": "TestCam", "exposure": "1/100s"}

    mock_db = AsyncMock()
    mock_image_storage = MagicMock()
    mock_image_storage.meta_data = expected_metadata

    with patch(
        "npo.modules.images.routes.get_image_by_pixel_hash", new_callable=AsyncMock
    ) as mock_get_image_infos:
        mock_get_image_infos.return_value = mock_image_storage

        metadata = await get_raw_metadata(pixel_hash, mock_db)

        assert metadata == expected_metadata

        mock_get_image_infos.assert_awaited_once_with(pixel_hash, mock_db)


async def test_get_metadata_photography_not_found():
    """
    Test that ValueError is raised when a required argument is missing.
    """
    pixel_hash = "test_hash_123"

    mock_db = AsyncMock()
    mock_image_storage = MagicMock()
    mock_image_storage.meta_data = None
    with patch(
        "npo.modules.images.routes.get_image_by_pixel_hash", new_callable=AsyncMock
    ) as mock_get_image_infos:
        mock_get_image_infos.return_value = None

        with pytest.raises(APIException) as exc_info:
            await get_photography_metadata(pixel_hash, mock_db)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail["code"] == ERROR_PHOTOGRAPHY_METADATA_NOT_FOUND
        assert (
            exc_info.value.detail["message"]
            == f"Photography metadata for file {pixel_hash} not found."
        )

        mock_get_image_infos.assert_awaited_once_with(pixel_hash, mock_db)


@patch("npo.modules.images.metadata_formatters._", new=lambda x: x)
async def test_get_metadata_photography_success():
    """
    Test that get_photography_metadata returns the correct metadata when found.
    """
    pixel_hash = "test_hash_123"
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
    mock_image_storage = MagicMock()
    mock_image_storage.meta_data = metadata

    with patch(
        "npo.modules.images.routes.get_image_by_pixel_hash", new_callable=AsyncMock
    ) as mock_get_image_infos:
        mock_get_image_infos.return_value = mock_image_storage

        metadata = await get_photography_metadata(pixel_hash, mock_db)

        assert metadata == expected_metadata

        mock_get_image_infos.assert_awaited_once_with(pixel_hash, mock_db)


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
