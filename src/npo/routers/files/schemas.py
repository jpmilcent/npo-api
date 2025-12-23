from pydantic import BaseModel


class File(BaseModel):
    """File data model."""

    name: str
    path: str
    mime: str | None = None
    size: int | None = None

    hash: str = ""
    hash_dir: str = ""
    hash_file: str = ""

    metadata: dict | None = None
