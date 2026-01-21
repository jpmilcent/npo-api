from npo.core.constants import ErrorCode


class DomainError(Exception):
    """Base class for domain exceptions."""

    def __init__(self, code: ErrorCode, **kwargs):
        self.code = code
        self.kwargs = kwargs


class DuplicateImageError(DomainError):
    """Exception raised when an image already exists."""

    pass


class InsufficientStorageError(DomainError):
    """Exception raised when there is not enough storage space."""

    pass


class FileTooLargeError(DomainError):
    """Exception raised when file size exceeds limit."""

    pass


class StorageError(DomainError):
    """Exception raised when storage operation fails."""

    pass


class ImageDecodingError(DomainError):
    """Exception raised when image decoding fails."""

    pass


class ImageProcessingError(DomainError):
    """Exception raised when image processing fails."""

    pass


class UnsupportedGpsDatumError(DomainError):
    """Exception raised when GPS datum is not supported."""

    pass
