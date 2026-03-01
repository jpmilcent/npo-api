from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from tests.constants import (
    ERROR_FORBIDDEN_IMAGE_ACCESS,
    ERROR_IMAGE_NOT_FOUND,
    ERROR_PHOTOGRAPHY_METADATA_NOT_FOUND,
    ERROR_RAW_METADATA_NOT_FOUND,
    MSG_FORBIDDEN_IMAGE_ACCESS,
    MSG_IMAGE_NOT_FOUND,
    MSG_PHOTOGRAPHY_METADATA_NOT_FOUND,
)

from npo.core.exceptions import APIException
from npo.modules.images.dependencies import (
    get_image_for_raw_metadata,
    get_image_for_raw_metadata_photography,
    get_image_for_user,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mock_current_user",
    [
        MagicMock(is_superadmin=True),
        MagicMock(is_superadmin=False, id=1),
    ],
)
async def test_get_image_for_user_success(mock_current_user):
    pixel_hash = "test_hash_123"
    mock_db = AsyncMock()

    with patch("npo.modules.images.dependencies.get_image_by_pixel_hash") as mock_get_image:
        mock_image = MagicMock()
        mock_image.user_id = 1
        mock_get_image.return_value = mock_image

        output_image = await get_image_for_user(pixel_hash, mock_db, mock_current_user)

    assert mock_get_image.call_count == 1
    assert output_image == mock_image


@pytest.mark.asyncio
async def test_get_image_for_user_no_image():
    pixel_hash = "test_hash_123"
    mock_db = AsyncMock()
    mock_current_user = MagicMock()
    mock_current_user.id = 1
    mock_current_user.is_superadmin = False

    with patch("npo.modules.images.dependencies.get_image_by_pixel_hash") as mock_get_image:
        mock_get_image.return_value = None

        with pytest.raises(APIException) as exc_info:
            await get_image_for_user(pixel_hash, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert isinstance(exc_info.value.detail, dict)
        detail = exc_info.value.detail
        assert detail.get("code") == ERROR_IMAGE_NOT_FOUND
        assert detail.get("message") == f"Image {pixel_hash} not found."


@pytest.mark.asyncio
async def test_get_image_for_user_forbidden_access():
    pixel_hash = "test_hash_123"
    mock_db = AsyncMock()
    mock_current_user = MagicMock()
    mock_current_user.id = 1
    mock_current_user.is_superadmin = False

    with patch("npo.modules.images.dependencies.get_image_by_pixel_hash") as mock_get_image:
        mock_image = MagicMock()
        mock_image.user_id = 2
        mock_get_image.return_value = mock_image

        with pytest.raises(APIException) as exc_info:
            await get_image_for_user(pixel_hash, mock_db, mock_current_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert isinstance(exc_info.value.detail, dict)
        detail = exc_info.value.detail
        assert detail.get("code") == ERROR_FORBIDDEN_IMAGE_ACCESS
        assert detail.get("message") == MSG_FORBIDDEN_IMAGE_ACCESS.format(pixel_hash=pixel_hash)


async def test_get_raw_metadata_not_found():
    """
    Test that get_image_for_raw_metadata raises a 404 when metadata is missing.
    """
    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_file_storage = MagicMock()
    mock_file_storage.meta_data = None
    mock_file_storage.pixel_hash = "test_hash_123"

    with patch(
        "npo.modules.images.dependencies.get_image_for_user", new_callable=AsyncMock
    ) as mock_get_image:
        mock_get_image.side_effect = APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="IMAGE_NOT_FOUND",
            message="Image not found",
        )
        with pytest.raises(APIException) as exc_info:
            await get_image_for_raw_metadata(mock_file_storage.pixel_hash, mock_db, mock_user)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail.get("code") == ERROR_RAW_METADATA_NOT_FOUND
    assert (
        exc_info.value.detail.get("message")
        == f"Raw metadata for file {mock_file_storage.pixel_hash} not found."
    )


async def test_get_raw_metadata_other_exception():
    """
    Test that get_image_for_raw_metadata raises an exception but not 404.
    """
    mock_db = AsyncMock()
    mock_user = MagicMock()
    pixel_hash = "test_hash_123"

    with patch(
        "npo.modules.images.dependencies.get_image_for_user", new_callable=AsyncMock
    ) as mock_get_image:
        mock_get_image.side_effect = APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code=ERROR_FORBIDDEN_IMAGE_ACCESS,
            message=MSG_FORBIDDEN_IMAGE_ACCESS.format(pixel_hash=pixel_hash),
        )
        with pytest.raises(APIException) as exc_info:
            await get_image_for_raw_metadata(pixel_hash, mock_db, mock_user)

    assert exc_info.value.status_code != status.HTTP_404_NOT_FOUND
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail.get("code") == ERROR_FORBIDDEN_IMAGE_ACCESS
    assert exc_info.value.detail.get("message") == MSG_FORBIDDEN_IMAGE_ACCESS.format(
        pixel_hash=pixel_hash
    )


async def test_get_metadata_photography_success():
    """
    Test that get_image_for_raw_metadata_photography return image data with photography metadata.
    """
    mock_db = AsyncMock()
    mock_user = MagicMock()
    pixel_hash = "test_hash_123"
    mock_meta_data = MagicMock()
    mock_meta_data.pixel_hash = pixel_hash

    mock_image = MagicMock()
    mock_image.meta_data = mock_meta_data

    with patch(
        "npo.modules.images.dependencies.get_image_for_user", new_callable=AsyncMock
    ) as mock_get_image:
        mock_get_image.return_value = mock_image
        out = await get_image_for_raw_metadata_photography(pixel_hash, mock_db, mock_user)

    assert out.meta_data.pixel_hash == pixel_hash


async def test_get_metadata_photography_metadata_not_found():
    """
    Test that get_image_for_raw_metadata_photography raises a 404 when metadata is missing.
    """
    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_file_storage = MagicMock()
    mock_file_storage.meta_data = None
    mock_file_storage.pixel_hash = "test_hash_123"

    with patch(
        "npo.modules.images.dependencies.get_image_for_user", new_callable=AsyncMock
    ) as mock_get_image:
        mock_get_image.return_value = mock_file_storage
        with pytest.raises(APIException) as exc_info:
            await get_image_for_raw_metadata_photography(
                mock_file_storage.pixel_hash, mock_db, mock_user
            )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert isinstance(exc_info.value.detail, dict)
    detail = exc_info.value.detail
    assert detail.get("code") == ERROR_PHOTOGRAPHY_METADATA_NOT_FOUND
    assert detail.get("message") == MSG_PHOTOGRAPHY_METADATA_NOT_FOUND.format(
        pixel_hash=mock_file_storage.pixel_hash
    )


async def test_get_metadata_photography_image_not_found_exception():
    """
    Test that get_image_for_raw_metadata_photography raises a 404 when image is not found.
    """
    mock_db = AsyncMock()
    mock_user = MagicMock()
    pixel_hash = "test_hash_123"

    with patch(
        "npo.modules.images.dependencies.get_image_for_user", new_callable=AsyncMock
    ) as mock_get_image:
        mock_get_image.side_effect = APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="fake_code",
            message="fake_message",
        )
        with pytest.raises(APIException) as exc_info:
            await get_image_for_raw_metadata_photography(pixel_hash, mock_db, mock_user)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert isinstance(exc_info.value.detail, dict)
    detail = exc_info.value.detail
    assert detail.get("code") == ERROR_IMAGE_NOT_FOUND
    assert detail.get("message") == MSG_IMAGE_NOT_FOUND.format(pixel_hash=pixel_hash)


async def test_get_metadata_photography_image_other_exception():
    """
    Test that get_image_for_raw_metadata_photography also raises other exceptions like 403.
    """
    mock_db = AsyncMock()
    mock_user = MagicMock()
    pixel_hash = "test_hash_123"

    with patch(
        "npo.modules.images.dependencies.get_image_for_user", new_callable=AsyncMock
    ) as mock_get_image:
        mock_get_image.side_effect = APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="fake_code",
            message="fake_message",
        )
        with pytest.raises(APIException) as exc_info:
            await get_image_for_raw_metadata_photography(pixel_hash, mock_db, mock_user)

    assert exc_info.value.status_code != status.HTTP_404_NOT_FOUND
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert isinstance(exc_info.value.detail, dict)
    detail = exc_info.value.detail
    assert detail.get("code") == "fake_code"
    assert detail.get("message") == "fake_message"
