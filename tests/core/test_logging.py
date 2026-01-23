from npo.core import config
from npo.core.logging import setup_logging


def test_make_log_directory(tmp_path):
    """
    Test that setup_logging creates the log directory if not exists.
    """
    logs_dir = tmp_path / "subdir" / "logs"

    # Patch the config to use our test logs directory
    original_logs_dir = config.settings.logs_dir
    config.settings.logs_dir = logs_dir

    try:
        setup_logging()
        assert logs_dir.exists(), "The log directory should have been created."
    finally:
        # Restore original logs directory
        config.settings.logs_dir = original_logs_dir
