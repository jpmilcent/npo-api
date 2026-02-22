from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from tests.constants import ERROR_PHOTOGRAPHY_METADATA_NOT_FOUND, ERROR_RAW_METADATA_NOT_FOUND

from npo.core.exceptions import APIException
from npo.modules.images.dependencies import (
    get_image_for_raw_metadata,
    get_image_for_raw_metadata_photography,
)


async def test_get_metadata_photography_not_found():
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
    assert (
        detail.get("message")
        == f"Photography metadata for file {mock_file_storage.pixel_hash} not found."
    )


async def test_get_raw_metadata_not_found():
    """
    Tet that get_image_for_raw_metadata raises a 404 when metadata is missing.
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
