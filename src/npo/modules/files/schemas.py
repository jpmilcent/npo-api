from datetime import datetime

from pydantic import BaseModel


class File(BaseModel):
    """File data model."""

    name: str
    path: str
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

    image_unique_id: str | None = None
    perceptual_hash: str | None = None
    pixel_hash: str | None = None
    file_hash: str = ""

    meta_data: dict | None = None


class PhotographyMetadata(BaseModel):
    """Schema for formatted photography metadata."""

    cameraMaker: str | None = None
    cameraModel: str | None = None
    lensModel: str | None = None
    focalLength: str | None = None
    focalLengthIn35mmFormat: str | None = None
    aperture: str | None = None
    shutterSpeed: str | None = None
    iso: int | str | None = None
    flash: str | None = None
    imageWidth: str | None = None
    imageHeight: str | None = None
    orientation: str | None = None
    whiteBalance: str | None = None
    exposureProgram: str | None = None
    exposureMode: str | None = None
    exposureCompensation: str | None = None
    meteringMode: str | None = None
    sceneCaptureType: str | None = None
    sceneType: str | None = None
    colorSpace: str | None = None
