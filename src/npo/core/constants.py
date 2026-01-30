from enum import StrEnum
from string import Formatter

from fastapi_babel import _
from pydantic import BaseModel, Field, ValidationError


def gettext_noop(message: str) -> str:
    return message


N_ = gettext_noop


class ErrorArguments(BaseModel):
    filename: str | None = Field(default=None, min_length=1)
    perceptual_hash: str | None = Field(default=None, min_length=16)
    pixel_hash: str | None = Field(default=None, min_length=8)
    path: str | None = Field(default=None, min_length=1)
    gps_datum: str | None = Field(default=None)
    image_unique_id: str | None = Field(default=None)
    zoom: int | None = Field(default=None, ge=0)
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)

    model_config = {"extra": "allow"}


# Error Codes
class ErrorCode(StrEnum):
    DUPLICATE_PERCEPTUAL_HASH = (
        "DUPLICATE_PERCEPTUAL_HASH",
        N_("Image {filename} with perceptual hash {perceptual_hash} already exists."),
    )
    DUPLICATE_IMAGE_UNIQUE_ID = (
        "DUPLICATE_IMAGE_UNIQUE_ID",
        N_("Image {filename} with image unique ID {image_unique_id} already exists."),
    )
    FILE_TOO_LARGE = ("FILE_TOO_LARGE", N_("File size exceeds the maximum allowed limit."))
    FILE_UPLOAD_ERROR = ("FILE_UPLOAD_ERROR", N_("There was an error uploading the file."))
    IMAGE_DECODING_ERROR = ("IMAGE_DECODING_ERROR", N_("Unable to decode image file {filename}."))
    IMAGE_NOT_FOUND = ("IMAGE_NOT_FOUND", N_("Image {pixel_hash} not found."))
    IMAGE_DZI_NOT_FOUND = (
        "IMAGE_DZI_NOT_FOUND",
        N_("DZI tile for image {pixel_hash} tile {zoom}/{x}/{y} not found."),
    )
    IMAGE_PROCESSING_ERROR = (
        "IMAGE_PROCESSING_ERROR",
        N_("Unable to process image file {filename} for perceptual hashing."),
    )
    IMAGES_WEBSERVICE_NOT_FOUND = (
        "IMAGES_WEBSERVICE_NOT_FOUND",
        N_("Webservice /images/{path} requested not found."),
    )
    INSUFFICIENT_STORAGE = (
        "INSUFFICIENT_STORAGE",
        N_("Not enough disk space to save the file."),
    )
    RAW_METADATA_NOT_FOUND = (
        "RAW_METADATA_NOT_FOUND",
        N_("Raw metadata for file {pixel_hash} not found."),
    )
    PHOTOGRAPHY_METADATA_NOT_FOUND = (
        "PHOTOGRAPHY_METADATA_NOT_FOUND",
        N_("Photography metadata for file {pixel_hash} not found."),
    )
    SETTINGS_WEBSERVICE_NOT_FOUND = (
        "SETTINGS_WEBSERVICE_NOT_FOUND",
        N_("Webservice /settings/{path} requested not found."),
    )
    SETTINGS_VERSION_NOT_FOUND = (
        "SETTINGS_VERSION_NOT_FOUND",
        N_(
            "The application version could not be determined for package '{package_name}'. "
            "Check if the package is installed."
        ),
    )
    UNSUPPORTED_GPS_DATUM = (
        "UNSUPPORTED_GPS_DATUM",
        N_(
            "Image {filename} has unsupported GPS Map Datum: {gps_datum}. Only WGS-84 is supported."
        ),
    )

    def __new__(cls, value, message):
        member = str.__new__(cls, value)
        member._value_ = value
        member.message = message
        return member

    def formatMsg(
        self,
        **kwargs,
    ) -> str:
        try:
            params = ErrorArguments(**kwargs)
        except ValidationError as e:
            raise ValueError(f"Invalid arguments for error {self.name}: {e}") from e

        args = params.model_dump(exclude_none=True)
        required_fields = [fname for _, fname, _, _ in Formatter().parse(self.message) if fname]
        missing = [field for field in required_fields if args.get(field) is None]
        if missing:
            raise ValueError(
                f"Missing required arguments for error {self.name}: {', '.join(missing)}"
            )
        return _(self.message).format(**args)
