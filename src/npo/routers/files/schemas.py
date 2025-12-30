from pydantic import BaseModel


class File(BaseModel):
    """File data model."""

    name: str
    path: str
    mime: str | None = None
    size: int | None = None
    orientation: int | None = None
    image_unique_id: str | None = None

    perceptual_hash: str | None = None
    pixel_hash: str | None = None
    hash: str = ""
    hash_dir: str = ""
    hash_file: str = ""

    meta_data: dict | None = None
