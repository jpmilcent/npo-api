from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, Field, RootModel

from npo.common.schemas import PaginatedResponse
from npo.core.i18n import _


class Image(BaseModel):
    """Image data model."""

    name: str | None = Field(default=None, description=_("Image file name."))
    path: str = Field(default="", description=_("Image file path."))
    path_hash_dir: str = Field(default="", description=_("Image hash part for directory path."))
    path_hash_file: str = Field(default="", description=_("Image hash part for file name."))
    mime: str | None = Field(default=None, description=_("Image MIME type."))
    size: int | None = Field(default=None, description=_("Image size in bytes."))
    orientation: int | None = Field(default=None, description=_("Image orientation."))

    latitude: float | None = Field(
        default=None, description=_("Image latitude extracted from metadata.")
    )
    longitude: float | None = Field(
        default=None, description=_("Image longitude extracted from metadata.")
    )
    altitude: float | None = Field(
        default=None, description=_("Image altitude extracted from metadata.")
    )

    datetime_shooting: datetime | None = Field(
        default=None, description=_("Image shooting date and time.")
    )
    datetime_digitized: datetime | None = Field(
        default=None, description=_("Image digitized date.")
    )

    image_unique_id: str | None = Field(default="", description=_("Image unique ID."))
    perceptual_hash: str = Field(default="", description=_("Image perceptual hash."))
    pixel_hash: str = Field(default="", description=_("Image pixel hash."))
    file_hash: str = Field(default="", description=_("Image file hash."))
    user_id: int | None = Field(
        default=None, description=_("ID of the user who uploaded the image.")
    )

    meta_data: dict | None = Field(
        default=None, description=_("Image metadata extracted with Exiftool.")
    )


class UploadResponse(RootModel[dict[str, Image]]):
    """Response model for the image upload endpoint, mapping filenames to image details."""

    model_config: ClassVar[dict] = {
        "json_schema_extra": {
            "examples": [
                {
                    "landscape.jpg": {
                        "name": "landscape.jpg",
                        "path": "/data/uploads/landscape.jpg",
                        "mime": "image/jpeg",
                        "size": 5242880,
                        "datetime_shooting": "2023-08-15T14:30:00",
                        "latitude": 48.8584,
                        "longitude": 2.2945,
                    }
                }
            ]
        }
    }


class PhotographyMetadata(BaseModel):
    """Schema for formatted photography metadata."""

    cameraMaker: str | None = Field(default=None, description=_("Camera manufacturer (e.g. Canon)"))
    cameraModel: str | None = Field(default=None, description=_("Camera model (e.g. EOS 5D)"))
    lensModel: str | None = Field(default=None, description=_("Lens model used"))
    focalLength: str | None = Field(default=None, description=_("Focal length (e.g. 50 mm)"))
    focalLengthIn35mmFormat: str | None = Field(
        default=None, description=_("35mm equivalent focal length")
    )
    aperture: str | None = Field(default=None, description=_("Aperture (e.g. f/2.8)"))
    shutterSpeed: str | None = Field(default=None, description=_("Shutter speed (e.g. 1/100)"))
    iso: int | str | None = Field(default=None, description=_("ISO sensitivity"))
    flash: str | None = Field(default=None, description=_("Flash status at capture"))
    imageWidth: str | None = Field(default=None, description=_("Image width in pixels"))
    imageHeight: str | None = Field(default=None, description=_("Image height in pixels"))
    orientation: str | None = Field(default=None, description=_("Image orientation"))
    whiteBalance: str | None = Field(default=None, description=_("White balance"))
    exposureProgram: str | None = Field(default=None, description=_("Exposure program"))
    exposureMode: str | None = Field(default=None, description=_("Exposure mode"))
    exposureCompensation: str | None = Field(
        default=None, description=_("Exposure compensation (EV)")
    )
    meteringMode: str | None = Field(default=None, description=_("Metering mode"))
    sceneCaptureType: str | None = Field(default=None, description=_("Scene capture type"))
    sceneType: str | None = Field(default=None, description=_("Scene type"))
    colorSpace: str | None = Field(default=None, description=_("Color space (e.g. sRGB)"))

    model_config: ClassVar[dict] = {
        "json_schema_extra": {
            "examples": [
                {
                    "cameraMaker": "Canon",
                    "cameraModel": "Canon EOS 5D Mark IV",
                    "lensModel": "EF24-105mm f/4L IS USM",
                    "focalLength": "50 mm",
                    "focalLengthIn35mmFormat": "50 mm",
                    "aperture": "f/8.0",
                    "shutterSpeed": "1/125",
                    "iso": 100,
                    "flash": "Flash did not fire, compulsory flash mode",
                    "imageWidth": "6720 px",
                    "imageHeight": "4480 px",
                    "orientation": "Horizontal (normal)",
                    "whiteBalance": "Auto",
                    "exposureProgram": "Aperture priority",
                    "exposureMode": "Auto",
                    "exposureCompensation": "+0.3 EV",
                    "meteringMode": "Pattern",
                    "sceneCaptureType": "Standard",
                    "sceneType": "Directly photographed",
                    "colorSpace": "sRGB",
                }
            ]
        }
    }


class ImageSummary(BaseModel):
    id: int = Field(description=_("Image database primary key ID."))
    hash: str = Field(description=_("Image pixel hash use for storage path."))
    name: str | None = Field(description=_("Image file name."))
    mime: str | None = Field(description=_("Image MIME type."))
    size: int | None = Field(description=_("Image size in bytes."))
    datetime_shooting: datetime | None = Field(description=_("Image shooting date and time."))
    latitude: float | None = Field(description=_("Image latitude extracted from metadata."))
    longitude: float | None = Field(description=_("Image longitude extracted from metadata."))
    created_at: datetime | None = Field(description=_("Image creation date and time."))
    updated_at: datetime | None = Field(description=_("Image update date and time."))


class ImageListResponse(PaginatedResponse[ImageSummary]):
    model_config: ClassVar[dict] = {
        "json_schema_extra": {
            "examples": [
                {
                    "meta": {
                        "pagination": {
                            "total_items": 1,
                            "total_pages": 1,
                            "current_page": 1,
                            "items_per_page": 100,
                        }
                    },
                    "data": [
                        {
                            "id": 123,
                            "hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
                            "name": "landscape_photo.jpg",
                            "mime": "image/jpeg",
                            "size": 5120345,
                            "datetime_shooting": "2023-08-15T14:30:00",
                            "latitude": 48.8584,
                            "longitude": 2.2945,
                            "created_at": "2023-10-27T15:00:00Z",
                            "updated_at": "2023-10-27T15:00:00Z",
                        }
                    ],
                }
            ]
        }
    }
