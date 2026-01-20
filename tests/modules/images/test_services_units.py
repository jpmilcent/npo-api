from unittest.mock import MagicMock, patch

import pytest
from fastapi import status

from npo.core.exceptions import APIException
from npo.modules.images.services import check_max_upload_size, check_required_space

# Define an arbitrary limit of 100 bytes for the upload size
TEST_UPLOAD_MAX_SIZE = 100
# Define an arbitrary limit of 100 bytes for the upload safety buffer
TEST_UPLOAD_SAFETY_BUFFER = 10


@patch("npo.core.config.backend_settings.max_upload_size", TEST_UPLOAD_MAX_SIZE)
def test_check_max_upload_size_success():
    """Verify that no exception is raised if the size is <= the limit."""
    # Case 1: Size is smaller
    check_max_upload_size(50)

    # Case 2: Size is exactly equal to the limit
    check_max_upload_size(100)


@patch("npo.core.config.backend_settings.max_upload_size", TEST_UPLOAD_MAX_SIZE)
def test_check_max_upload_size_failure():
    """Verify that an APIException is raised if the size exceeds the limit."""
    with pytest.raises(APIException) as exc_info:
        check_max_upload_size(101)

    assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert exc_info.value.detail["code"] == "FILE_TOO_LARGE"


@patch("npo.modules.images.services.shutil.disk_usage")
@patch("npo.core.config.backend_settings.upload_safety_buffer", TEST_UPLOAD_SAFETY_BUFFER)
def test_check_required_space_success(mock_disk_usage):
    """Verify that no exception is raised if there is enough disk space."""
    # Mock the image object
    mock_image = MagicMock()
    mock_image.path = "/tmp/test.jpg"

    # Case 1: Unknown size (None), free space (20) > buffer (10)
    mock_image.size = None
    mock_disk_usage.return_value = (100, 50, 20)  # total, used, free
    check_required_space(mock_image)

    # Case 2: Known size (50), free space (60) >= buffer (10) + size (50)
    mock_image.size = 50
    mock_disk_usage.return_value = (100, 40, 60)
    check_required_space(mock_image)


@patch("npo.modules.images.services.shutil.disk_usage")
@patch("npo.core.config.backend_settings.upload_safety_buffer", TEST_UPLOAD_SAFETY_BUFFER)
def test_check_required_space_failure(mock_disk_usage):
    """Verify that an APIException is raised if disk space is insufficient."""
    mock_image = MagicMock()
    mock_image.path = "/tmp/test.jpg"

    # Case 1: Unknown size, free space (5) < buffer (10)
    mock_image.size = None
    mock_disk_usage.return_value = (100, 95, 5)

    with pytest.raises(APIException) as exc_info:
        check_required_space(mock_image)

    assert exc_info.value.status_code == status.HTTP_507_INSUFFICIENT_STORAGE
    assert exc_info.value.detail["code"] == "INSUFFICIENT_STORAGE"

    # Case 2: Known size (50), free space (59) < buffer (10) + size (50)
    mock_image.size = 50
    mock_disk_usage.return_value = (100, 41, 59)

    with pytest.raises(APIException) as exc_info:
        check_required_space(mock_image)

    assert exc_info.value.status_code == status.HTTP_507_INSUFFICIENT_STORAGE
