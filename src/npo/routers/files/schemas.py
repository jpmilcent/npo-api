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
