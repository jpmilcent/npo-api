import pytest

from npo.core.config import BackendSettings


def test_validate_log_level_value_error():
    """
    Test that ValueError is raised when log level entry is not valid.
    """
    with pytest.raises(
        ValueError, match=r"Log level must be DEBUG, INFO, WARNING, ERROR or CRITICAL"
    ):
        BackendSettings.validate_log_level("INVALID_LOG_LEVEL")


def test_parse_human_readable_size_valid_formats():
    """
    Test that human-readable size strings are correctly parsed to integers.
    """
    ONE_UNDRED_BYTES = 100
    TWO_KB = 2 * 1024
    assert BackendSettings.parse_human_readable_size("10MB") == 10 * 1024 * 1024
    assert BackendSettings.parse_human_readable_size("1GB") == 1 * 1024 * 1024 * 1024
    assert BackendSettings.parse_human_readable_size("500KB") == 500 * 1024
    assert BackendSettings.parse_human_readable_size("100B") == ONE_UNDRED_BYTES
    assert BackendSettings.parse_human_readable_size(2048) == TWO_KB
    assert BackendSettings.parse_human_readable_size("2048") == TWO_KB
    assert BackendSettings.parse_human_readable_size("2048").is_integer()
    assert BackendSettings.parse_human_readable_size("2.5MB") == int(2.5 * 1024 * 1024)
    assert BackendSettings.parse_human_readable_size("  20 GB ") == 20 * 1024 * 1024 * 1024
    assert BackendSettings.parse_human_readable_size("0B") == 0
    assert BackendSettings.parse_human_readable_size("0") == 0
    assert BackendSettings.parse_human_readable_size(0) == 0


def test_parse_human_readable_size_invalid_formats():
    """
    Test that ValueError is raised when size string format is invalid.
    """
    with pytest.raises(
        ValueError, match=r"Invalid size format: 10XYZ. Expected format like '10MB', '1GB'."
    ):
        BackendSettings.parse_human_readable_size("10XYZ")

    with pytest.raises(ValueError, match="Invalid size format"):
        BackendSettings(
            log_max_bytes="ABCmb",  # "mb" matching, but "abc" not a valid number
        )

    with pytest.raises(ValueError, match="Invalid size format"):
        BackendSettings(
            upload_safety_buffer="12.34.56GB",  # Invalid number format
        )

    with pytest.raises(ValueError, match="Invalid size format"):
        BackendSettings(
            max_upload_size="--100MB",  # Invalid number format
        )
