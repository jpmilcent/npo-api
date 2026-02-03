from datetime import datetime

from pydantic import BaseModel, Field

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
