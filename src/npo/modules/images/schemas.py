from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, Field

from npo.common.schemas import PaginatedResponse
from npo.core.i18n import _


class Image(BaseModel):
    """Image data model."""

    name: str | None = None
    path: str = ""
    path_hash_dir: str = ""
    path_hash_file: str = ""
    mime: str | None = None
    size: int | None = None
    orientation: int | None = None

    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None

    datetime_shooting: datetime | None = None
    datetime_digitized: datetime | None = None

    image_unique_id: str | None = ""
    perceptual_hash: str = ""
    pixel_hash: str = ""
    file_hash: str = ""

    meta_data: dict | None = None


class PhotographyMetadata(BaseModel):
    """Schema for formatted photography metadata."""

    cameraMaker: str | None = Field(None, description=_("Camera manufacturer (e.g. Canon)"))
    cameraModel: str | None = Field(None, description=_("Camera model (e.g. EOS 5D)"))
    lensModel: str | None = Field(None, description=_("Lens model used"))
    focalLength: str | None = Field(None, description=_("Focal length (e.g. 50 mm)"))
    focalLengthIn35mmFormat: str | None = Field(None, description=_("35mm equivalent focal length"))
    aperture: str | None = Field(None, description=_("Aperture (e.g. f/2.8)"))
    shutterSpeed: str | None = Field(None, description=_("Shutter speed (e.g. 1/100)"))
    iso: int | str | None = Field(None, description=_("ISO sensitivity"))
    flash: str | None = Field(None, description=_("Flash status at capture"))
    imageWidth: str | None = Field(None, description=_("Image width in pixels"))
    imageHeight: str | None = Field(None, description=_("Image height in pixels"))
    orientation: str | None = Field(None, description=_("Image orientation"))
    whiteBalance: str | None = Field(None, description=_("White balance"))
    exposureProgram: str | None = Field(None, description=_("Exposure program"))
    exposureMode: str | None = Field(None, description=_("Exposure mode"))
    exposureCompensation: str | None = Field(None, description=_("Exposure compensation (EV)"))
    meteringMode: str | None = Field(None, description=_("Metering mode"))
    sceneCaptureType: str | None = Field(None, description=_("Scene capture type"))
    sceneType: str | None = Field(None, description=_("Scene type"))
    colorSpace: str | None = Field(None, description=_("Color space (e.g. sRGB)"))


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
