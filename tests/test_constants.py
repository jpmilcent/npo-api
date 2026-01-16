import pytest

from npo.core.constants import ErrorCode


def test_format_msg_success():
    """
    Test that formatting works correctly when all required arguments are provided.
    """
    # Case with 1 argument
    msg = ErrorCode.FILE_NOT_FOUND.formatMsg(pixel_hash="a" * 32)
    assert msg == f"File {'a' * 32} not found."

    # Case with multiple arguments
    msg = ErrorCode.DUPLICATE_PERCEPTUAL_HASH.formatMsg(
        filename="photo.jpg", perceptual_hash="a" * 16
    )
    assert msg == f"File photo.jpg with perceptual hash {'a' * 16} already exists."


def test_format_msg_missing_argument():
    """
    Test that ValueError is raised when a required argument is missing.
    """
    with pytest.raises(
        ValueError, match=r"Missing required arguments for error FILE_NOT_FOUND: pixel_hash"
    ):
        ErrorCode.FILE_NOT_FOUND.formatMsg()


def test_format_msg_empty_argument():
    """
    Test that ValueError is raised when an argument is provided but empty.
    The validation logic `if not args.get(field)` treats empty strings as missing.
    """
    # Use regex .* to match both the wrapper message and the specific Pydantic error
    with pytest.raises(
        ValueError,
        match=(
            r"(?s)Invalid arguments for error FILE_NOT_FOUND.*"
            r"String should have at least 32 characters"
        ),
    ):
        # Providing an empty string should fail validation
        ErrorCode.FILE_NOT_FOUND.formatMsg(pixel_hash="")


def test_format_msg_invalid_length():
    """
    Test that ValueError is raised when an argument is too short (Pydantic validation).
    """
    with pytest.raises(
        ValueError,
        match=(
            r"(?s)Invalid arguments for error FILE_NOT_FOUND.*"
            r"String should have at least 32 characters"
        ),
    ):
        # pixel_hash requires 32 chars, providing only 5
        ErrorCode.FILE_NOT_FOUND.formatMsg(pixel_hash="12345")
