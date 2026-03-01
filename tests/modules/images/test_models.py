from unittest.mock import MagicMock, call, patch

import pytest

from npo.modules.images.models import delete_image_files


async def test_delete_image_files_success():
    mapper = MagicMock()
    connection = MagicMock()
    target = MagicMock()
    target.path_hash_dir = "test_dir"
    target.path_hash_file = "test_file"
    files_list = ["test_file1", "test_file2"]

    with (
        patch("npo.modules.images.models.backend_settings.storage_dir", "test_storage_dir"),
        patch("npo.modules.images.models.os") as mock_os,
        patch("npo.modules.images.models.logger") as mock_logger,
    ):
        mock_os.path.join.side_effect = lambda *args: "/".join(args)
        mock_os.path.exists.return_value = True
        mock_os.listdir.return_value = files_list
        mock_os.remove.return_value = None

        delete_image_files(mapper, connection, target)

    assert mock_logger.info.call_count == len(files_list)
    assert mock_os.remove.call_count == len(files_list)
    expected_calls = [
        call("test_storage_dir/test_dir/test_file1"),
        call("test_storage_dir/test_dir/test_file2"),
    ]
    mock_os.remove.assert_has_calls(expected_calls, any_order=True)


async def test_delete_image_files_os_error():
    mapper = MagicMock()
    connection = MagicMock()
    target = MagicMock()
    target.path_hash_dir = "test_dir"
    target.path_hash_file = "test_file"
    files_list = ["test_file1"]

    with (
        patch("npo.modules.images.models.backend_settings.storage_dir", "test_storage_dir"),
        patch("npo.modules.images.models.os") as mock_os,
        patch("npo.modules.images.models.logger") as mock_logger,
    ):
        mock_os.path.join.side_effect = lambda *args: "/".join(args)
        mock_os.path.exists.return_value = True
        mock_os.listdir.return_value = files_list
        mock_os.remove.side_effect = OSError("Test error")

        delete_image_files(mapper, connection, target)

    assert mock_logger.error.call_count == len(files_list)
    mock_logger.error.assert_called_with(
        "Error deleting file test_storage_dir/test_dir/test_file1: Test error"
    )


async def test_delete_image_files_dir_access_error():
    mapper = MagicMock()
    connection = MagicMock()
    target = MagicMock()
    target.path_hash_dir = "test_dir"
    target.path_hash_file = "test_file"

    with (
        patch("npo.modules.images.models.backend_settings.storage_dir", "test_storage_dir"),
        patch("npo.modules.images.models.os") as mock_os,
        patch("npo.modules.images.models.logger") as mock_logger,
    ):
        mock_os.path.join.side_effect = lambda *args: "/".join(args)
        mock_os.path.exists.return_value = True
        mock_os.listdir.side_effect = OSError("Test error")

        delete_image_files(mapper, connection, target)

    assert (
        mock_logger.error.call_args[0][0]
        == "Error accessing directory test_storage_dir/test_dir: Test error"
    )
    mock_os.remove.assert_not_called()


@pytest.mark.parametrize(
    ("path_hash_dir", "path_hash_file"),
    [
        (None, None),
        ("test_dir", None),
        (None, "test_file"),
    ],
)
def test_delete_image_files_hash_file_or_dir_missing(path_hash_dir, path_hash_file):
    mapper = MagicMock()
    connection = MagicMock()
    target = MagicMock()
    target.path_hash_dir = path_hash_dir
    target.path_hash_file = path_hash_file

    out = delete_image_files(mapper, connection, target)

    assert out is None
