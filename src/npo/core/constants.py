from enum import StrEnum
from string import Formatter

from pydantic import BaseModel, Field, ValidationError


class ErrorArguments(BaseModel):
    filename: str | None = Field(default=None, min_length=1)
    perceptual_hash: str | None = Field(default=None, min_length=16)
    pixel_hash: str | None = Field(default=None, min_length=32)
    path: str | None = Field(default=None, min_length=1)

    model_config = {"extra": "allow"}


# Error Codes
class ErrorCode(StrEnum):
    DUPLICATE_PERCEPTUAL_HASH = (
        "DUPLICATE_PERCEPTUAL_HASH",
        "File {filename} with perceptual hash {perceptual_hash} already exists.",
    )
    FILE_NOT_FOUND = "FILE_NOT_FOUND", "File {pixel_hash} not found."
    FILES_WEBSERVICE_NOT_FOUND = (
        "FILES_WEBSERVICE_NOT_FOUND",
        "Webservice /files/{path} requested not found.",
    )
    RAW_METADATA_NOT_FOUND = (
        "RAW_METADATA_NOT_FOUND",
        "Raw metadata for file {pixel_hash} not found.",
    )
    PHOTOGRAPHY_METADATA_NOT_FOUND = (
        "PHOTOGRAPHY_METADATA_NOT_FOUND",
        "Photography metadata for file {pixel_hash} not found.",
    )
    SETTINGS_WEBSERVICE_NOT_FOUND = (
        "SETTINGS_WEBSERVICE_NOT_FOUND",
        "Webservice /settings/{path} requested not found.",
    )
    SETTINGS_VERSION_NOT_FOUND = (
        "SETTINGS_VERSION_NOT_FOUND",
        (
            "The application version could not be determined for package '{package_name}'. "
            "Check if the package is installed."
        ),
    )

    def __new__(cls, value, message):
        member = str.__new__(cls, value)
        member._value_ = value
        member.message = message
        return member

    def formatMsg(
        self,
        filename: str | None = None,
        perceptual_hash: str | None = None,
        pixel_hash: str | None = None,
        path: str | None = None,
        **kwargs,
    ) -> str:
        try:
            params = ErrorArguments(
                filename=filename,
                perceptual_hash=perceptual_hash,
                pixel_hash=pixel_hash,
                path=path,
                **kwargs,
            )
        except ValidationError as e:
            raise ValueError(f"Invalid arguments for error {self.name}: {e}") from e

        args = params.model_dump(exclude_none=True)
        required_fields = [fname for _, fname, _, _ in Formatter().parse(self.message) if fname]
        missing = [field for field in required_fields if not args.get(field)]
        if missing:
            raise ValueError(
                f"Missing required arguments for error {self.name}: {', '.join(missing)}"
            )
        return self.message.format(**args)
